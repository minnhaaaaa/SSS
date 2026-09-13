from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from types import MappingProxyType
from typing import Any, Protocol
from urllib.parse import quote
from uuid import uuid4

from sss_core.auth import CredentialAuditRecord
from sss_core.demo import FixedDemoFixture
from sss_core.domain import (
    CandidateStatus,
    Decision,
    Ecosystem,
    EvidenceScores,
    InstallRequest,
    PackageIdentity,
    PolicyDecision,
    RegistryStatus,
)
from sss_core.repositories.operations import (
    ApprovalNonceConflict,
    IdempotencyClaim,
    IdempotencyConflict,
    InstallAttempt,
    Intervention,
    InterventionStatus,
    OperationalEvent,
)


class ExasolResult(Protocol):
    def fetchall(self) -> Sequence[Sequence[Any]]: ...


class ExasolConnection(Protocol):
    def execute(
        self,
        sql: str,
        query_params: Mapping[str, Any] | None = None,
    ) -> ExasolResult | Sequence[Sequence[Any]]: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


def _rows(result: ExasolResult | Sequence[Sequence[Any]]) -> Sequence[Sequence[Any]]:
    if hasattr(result, "fetchall"):
        return result.fetchall()
    return result


def _statements(document: str) -> tuple[str, ...]:
    lines = [line for line in document.splitlines() if not line.lstrip().startswith("--")]
    statements = "\n".join(lines).split(";")
    return tuple(statement.strip() for statement in statements if statement.strip())


def _file_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()


def _exasol_timestamp(value: datetime) -> datetime:
    """Bind instants to Exasol's timezone-free TIMESTAMP columns as naive UTC."""
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _utc_timestamp(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _affected_rows(result: object) -> int:
    rowcount = getattr(result, "rowcount", 0)
    return int(rowcount() if callable(rowcount) else rowcount)


class MigrationRunner:
    def __init__(self, migrations_directory: Path) -> None:
        self._directory = migrations_directory

    def migrate(self, connection: ExasolConnection) -> tuple[str, ...]:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS SCHEMA_MIGRATIONS ("
            "VERSION VARCHAR(200) PRIMARY KEY, CHECKSUM VARCHAR(64) NOT NULL, "
            "APPLIED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        applied: list[str] = []
        try:
            for path in sorted(self._directory.glob("[0-9][0-9][0-9]_*.sql")):
                version = path.stem
                existing = connection.execute(
                    "SELECT VERSION FROM SCHEMA_MIGRATIONS WHERE VERSION = {version}",
                    {"version": version},
                )
                if _rows(existing):
                    continue
                document = path.read_text(encoding="utf-8")
                for statement in _statements(document):
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO SCHEMA_MIGRATIONS (VERSION, CHECKSUM, APPLIED_AT) "
                    "VALUES ({version}, {checksum}, CURRENT_TIMESTAMP)",
                    {
                        "version": version,
                        "checksum": _file_checksum(path),
                    },
                )
                applied.append(version)
            if applied:
                views_directory = self._directory.parent / "views"
                for path in sorted(views_directory.glob("*.sql")):
                    for statement in _statements(path.read_text(encoding="utf-8")):
                        connection.execute(statement)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return tuple(applied)


_VIEW_NAME = re.compile(r"CREATE\s+OR\s+REPLACE\s+VIEW\s+([A-Z0-9_]+)", re.IGNORECASE)


@dataclass(frozen=True)
class SchemaReadiness:
    expected_version: str | None
    current_version: str | None
    missing_migrations: tuple[str, ...]
    unexpected_migrations: tuple[str, ...]
    checksum_mismatches: tuple[str, ...]
    missing_views: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not (
            self.missing_migrations
            or self.unexpected_migrations
            or self.checksum_mismatches
            or self.missing_views
        )


class SchemaReadinessChecker:
    def __init__(self, migrations_directory: Path) -> None:
        self._migrations_directory = migrations_directory

    def check(self, connection: ExasolConnection) -> SchemaReadiness:
        expected = {
            path.stem: _file_checksum(path)
            for path in sorted(self._migrations_directory.glob("[0-9][0-9][0-9]_*.sql"))
        }
        migration_rows = _rows(
            connection.execute("SELECT VERSION, CHECKSUM FROM SCHEMA_MIGRATIONS ORDER BY VERSION")
        )
        applied = {str(row[0]): str(row[1]) for row in migration_rows}
        views_directory = self._migrations_directory.parent / "views"
        required_views: set[str] = set()
        for path in sorted(views_directory.glob("*.sql")):
            match = _VIEW_NAME.search(path.read_text(encoding="utf-8"))
            if match is None:
                raise ValueError(f"view file does not declare a view: {path}")
            required_views.add(match.group(1).upper())
        view_rows = _rows(
            connection.execute(
                "SELECT VIEW_NAME FROM EXA_ALL_VIEWS WHERE VIEW_SCHEMA = CURRENT_SCHEMA"
            )
        )
        available_views = {str(row[0]).upper() for row in view_rows}
        return SchemaReadiness(
            expected_version=max(expected, default=None),
            current_version=max(applied, default=None),
            missing_migrations=tuple(sorted(set(expected) - set(applied))),
            unexpected_migrations=tuple(sorted(set(applied) - set(expected))),
            checksum_mismatches=tuple(
                sorted(
                    version
                    for version in expected
                    if applied.get(version) not in {None, expected[version]}
                )
            ),
            missing_views=tuple(sorted(required_views - available_views)),
        )


@dataclass(frozen=True)
class RegistryEvidenceRecord:
    check_id: str
    package: PackageIdentity
    endpoint: str
    status: RegistryStatus
    http_status: int | None
    checked_at: datetime
    response_sha256: str | None
    error_class: str | None


class ExasolEvidenceRepository:
    def __init__(self, connection: ExasolConnection) -> None:
        self._connection = connection

    def store_evidence_and_transition(
        self,
        evidence: RegistryEvidenceRecord,
        candidate_status: CandidateStatus,
    ) -> None:
        parameters = {
            "check_id": evidence.check_id,
            "ecosystem": evidence.package.ecosystem.value,
            "registry_origin": evidence.package.registry_origin,
            "canonical_name": evidence.package.canonical_name,
            "endpoint": evidence.endpoint,
            "status": evidence.status.value,
            "http_status": evidence.http_status,
            "checked_at": _exasol_timestamp(evidence.checked_at),
            "response_sha256": evidence.response_sha256,
            "error_class": evidence.error_class,
            "candidate_status": candidate_status.value,
        }
        try:
            self._connection.execute(
                "INSERT INTO REGISTRY_CHECKS (CHECK_ID, ECOSYSTEM, REGISTRY_ORIGIN, "
                "CANONICAL_NAME, ENDPOINT, STATUS, HTTP_STATUS, CHECKED_AT, RESPONSE_SHA256, "
                "ERROR_CLASS) VALUES ({check_id}, {ecosystem}, {registry_origin}, "
                "{canonical_name}, {endpoint}, {status}, {http_status}, {checked_at}, "
                "{response_sha256}, {error_class})",
                parameters,
            )
            self._connection.execute(
                "MERGE INTO CANDIDATES C USING (SELECT {ecosystem} ECOSYSTEM, "
                "{registry_origin} REGISTRY_ORIGIN, {canonical_name} CANONICAL_NAME FROM DUAL) S "
                "ON C.ECOSYSTEM=S.ECOSYSTEM AND C.REGISTRY_ORIGIN=S.REGISTRY_ORIGIN "
                "AND C.CANONICAL_NAME=S.CANONICAL_NAME WHEN MATCHED THEN UPDATE SET "
                "C.STATUS={candidate_status}, C.FIRST_REGISTRATION_AT={checked_at} "
                "WHEN NOT MATCHED THEN INSERT (ECOSYSTEM, REGISTRY_ORIGIN, CANONICAL_NAME, "
                "STATUS, FIRST_REGISTRATION_AT, DISCLOSURE_CLASS, SYNTHETIC) VALUES "
                "({ecosystem}, {registry_origin}, {canonical_name}, {candidate_status}, "
                "{checked_at}, 'restricted_target_intelligence', FALSE)",
                parameters,
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise


class ExasolRadarRepository:
    def __init__(self, connection: ExasolConnection) -> None:
        self._connection = connection

    def list_private(self, *, limit: int = 100) -> list[dict[str, object]]:
        result = self._connection.execute(
            "SELECT * FROM V_RADAR_PRIVATE ORDER BY VERIFIED_MODEL_RECOMMENDATIONS DESC "
            "LIMIT {limit!d}",
            {"limit": limit},
        )
        return [{str(index): value for index, value in enumerate(row)} for row in _rows(result)]


class ExasolPolicyRepository:
    def __init__(self, connection: ExasolConnection) -> None:
        self._connection = connection

    def load_evidence(self, *, ecosystem: str, origin: str, name: str) -> dict[str, object]:
        result = self._connection.execute(
            "SELECT ECOSYSTEM, REGISTRY_ORIGIN, CANONICAL_NAME, STATUS, "
            "VERIFIED_MODEL_RECOMMENDATIONS, MODEL_CONFIGURATIONS, "
            "PROTECTED_AGENT_ATTEMPTS, PUBLIC_FAILED_REFERENCES, OBSERVATION_DAYS "
            "FROM V_RADAR_PRIVATE WHERE ECOSYSTEM={ecosystem} "
            "AND REGISTRY_ORIGIN={origin} AND CANONICAL_NAME={name}",
            {"ecosystem": ecosystem, "origin": origin, "name": name},
        )
        rows = _rows(result)
        if not rows:
            return {}
        columns = (
            "ECOSYSTEM",
            "REGISTRY_ORIGIN",
            "CANONICAL_NAME",
            "STATUS",
            "VERIFIED_MODEL_RECOMMENDATIONS",
            "MODEL_CONFIGURATIONS",
            "PROTECTED_AGENT_ATTEMPTS",
            "PUBLIC_FAILED_REFERENCES",
            "OBSERVATION_DAYS",
        )
        return dict(zip(columns, rows[0], strict=True))


def _request_payload(request: InstallRequest) -> dict[str, object]:
    return {
        "request_id": request.request_id,
        "project_id": request.project_id,
        "agent_family": request.agent_family,
        "package": {
            "ecosystem": request.package.ecosystem.value,
            "registry_origin": request.package.registry_origin,
            "canonical_name": request.package.canonical_name,
        },
        "version_spec": request.version_spec,
        "direct_url": request.direct_url,
        "artifact_sha256": request.artifact_sha256,
        "is_direct": request.is_direct,
    }


def _decision_payload(decision: PolicyDecision) -> dict[str, object]:
    return {
        "decision_id": decision.decision_id,
        "request_id": decision.request_id,
        "decision": decision.decision.value,
        "reason_codes": list(decision.reason_codes),
        "scores": {
            "absence_confidence": decision.scores.absence_confidence,
            "target_attractiveness": decision.scores.target_attractiveness,
            "package_policy_risk": decision.scores.package_policy_risk,
        },
        "policy_version": decision.policy_version,
        "expires_at": decision.expires_at.isoformat() if decision.expires_at else None,
    }


def _request_from_json(document: str) -> InstallRequest:
    payload = json.loads(document)
    package = payload["package"]
    return InstallRequest(
        request_id=str(payload["request_id"]),
        project_id=str(payload["project_id"]),
        agent_family=str(payload["agent_family"]),
        package=PackageIdentity(
            ecosystem=Ecosystem(str(package["ecosystem"])),
            registry_origin=str(package["registry_origin"]),
            canonical_name=str(package["canonical_name"]),
        ),
        version_spec=payload["version_spec"],
        direct_url=payload["direct_url"],
        artifact_sha256=payload["artifact_sha256"],
        is_direct=bool(payload["is_direct"]),
    )


def _decision_from_json(document: str) -> PolicyDecision:
    payload = json.loads(document)
    scores = payload["scores"]
    expires_at = payload["expires_at"]
    return PolicyDecision(
        decision_id=str(payload["decision_id"]),
        request_id=str(payload["request_id"]),
        decision=Decision(str(payload["decision"])),
        reason_codes=tuple(str(code) for code in payload["reason_codes"]),
        scores=EvidenceScores(
            absence_confidence=(
                None
                if scores["absence_confidence"] is None
                else int(scores["absence_confidence"])
            ),
            target_attractiveness=int(scores["target_attractiveness"]),
            package_policy_risk=int(scores["package_policy_risk"]),
        ),
        policy_version=str(payload["policy_version"]),
        expires_at=datetime.fromisoformat(str(expires_at)) if expires_at is not None else None,
    )


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")


class ExasolOperationalRepository:
    """Transactional Exasol persistence for Guard operational state."""

    def __init__(self, connection: ExasolConnection) -> None:
        self._connection = connection

    def record_credential_audit(self, record: CredentialAuditRecord) -> None:
        parameters = {
            "audit_id": record.audit_id,
            "credential_id": record.credential_id,
            "action_type": "authenticate",
            "request_id": record.request_id,
            "occurred_at": _exasol_timestamp(record.occurred_at),
            "metadata_json": _json(
                {
                    "route": record.route,
                    "required_scope": record.required_scope,
                    "outcome": record.outcome,
                }
            ),
        }
        try:
            self._connection.execute(
                "INSERT INTO CREDENTIAL_AUDIT (AUDIT_ID, CREDENTIAL_ID, ACTION_TYPE, "
                "REQUEST_ID, OCCURRED_AT, METADATA_JSON) VALUES ({audit_id}, "
                "{credential_id}, {action_type}, {request_id}, {occurred_at}, "
                "{metadata_json})",
                parameters,
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def record_decision(
        self,
        request: InstallRequest,
        decision: PolicyDecision,
        *,
        evidence_as_of: datetime,
        evidence_attestation: str,
    ) -> None:
        parameters = {
            "decision_id": decision.decision_id,
            "request_id": decision.request_id,
            "ecosystem": request.package.ecosystem.value,
            "registry_origin": request.package.registry_origin,
            "canonical_name": request.package.canonical_name,
            "absence_confidence": decision.scores.absence_confidence,
            "target_attractiveness": decision.scores.target_attractiveness,
            "package_policy_risk": decision.scores.package_policy_risk,
            "decision": decision.decision.value,
            "reason_codes_json": _json(list(decision.reason_codes)),
            "policy_version": decision.policy_version,
            "decided_at": _exasol_timestamp(evidence_as_of),
            "request_json": _json(_request_payload(request)),
            "evidence_as_of": _exasol_timestamp(evidence_as_of),
            "evidence_attestation": evidence_attestation,
        }
        try:
            self._connection.execute(
                "INSERT INTO POLICY_DECISIONS (DECISION_ID, REQUEST_ID, ECOSYSTEM, "
                "REGISTRY_ORIGIN, CANONICAL_NAME, ABSENCE_CONFIDENCE, TARGET_ATTRACTIVENESS, "
                "PACKAGE_POLICY_RISK, DECISION, REASON_CODES_JSON, POLICY_VERSION, DECIDED_AT, "
                "REQUEST_JSON, EVIDENCE_AS_OF, EVIDENCE_ATTESTATION) VALUES ({decision_id}, "
                "{request_id}, {ecosystem}, {registry_origin}, {canonical_name}, "
                "{absence_confidence}, {target_attractiveness}, {package_policy_risk}, "
                "{decision}, {reason_codes_json}, {policy_version}, {decided_at}, "
                "{request_json}, {evidence_as_of}, {evidence_attestation})",
                parameters,
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def record_attempt(
        self, attempt: InstallAttempt, *, attempt_id: str | None = None
    ) -> InstallAttempt:
        canonical_attempt = _json(
            {
                "decision_id": attempt.decision_id,
                "manager": attempt.manager,
                "arguments": list(attempt.arguments),
                "agent_family": attempt.agent_family,
                "project_id": attempt.project_id,
                "decision": attempt.decision.value,
                "child_started": attempt.child_started,
                "attempted_at": _exasol_timestamp(attempt.attempted_at).isoformat(),
            }
        )
        parameters = {
            "attempt_id": attempt_id or hashlib.sha256(canonical_attempt.encode()).hexdigest(),
            "decision_id": attempt.decision_id,
            "command_sha256": hashlib.sha256(
                _json([attempt.manager, *attempt.arguments]).encode()
            ).hexdigest(),
            "manager": attempt.manager,
            "arguments_json": _json(list(attempt.arguments)),
            "agent_family": attempt.agent_family,
            "project_id": attempt.project_id,
            "decision": attempt.decision.value,
            "child_started": attempt.child_started,
            "attempted_at": _exasol_timestamp(attempt.attempted_at),
        }
        for retry in range(5):
            try:
                self._connection.execute(
                    "INSERT INTO INSTALL_ATTEMPTS (ATTEMPT_ID, DECISION_ID, COMMAND_SHA256, "
                    "MANAGER, ARGUMENTS_JSON, AGENT_FAMILY, PROJECT_PSEUDONYM, DECISION, "
                    "CHILD_STARTED, ATTEMPTED_AT) VALUES ({attempt_id}, {decision_id}, "
                    "{command_sha256}, {manager}, {arguments_json}, {agent_family}, "
                    "{project_id}, {decision}, {child_started}, {attempted_at})",
                    parameters,
                )
                self._connection.commit()
                return attempt
            except Exception:
                self._connection.rollback()
                existing = self.get_attempt(str(parameters["attempt_id"]))
                if existing is not None:
                    if existing == attempt:
                        return existing
                    break
                if retry < 4:
                    sleep(0.02 * (retry + 1))
        raise RuntimeError("attempt could not be persisted after transaction collisions")

    @staticmethod
    def _attempt(row: Sequence[Any]) -> InstallAttempt:
        return InstallAttempt(
            decision_id=str(row[1]),
            manager=str(row[2]),
            arguments=tuple(str(value) for value in json.loads(str(row[3]))),
            agent_family=str(row[4]),
            project_id=str(row[5]),
            decision=Decision(str(row[6])),
            child_started=bool(row[7]),
            attempted_at=_utc_timestamp(row[8]),
        )

    def get_attempt(self, attempt_id: str) -> InstallAttempt | None:
        rows = _rows(
            self._connection.execute(
                "SELECT ATTEMPT_ID, DECISION_ID, MANAGER, ARGUMENTS_JSON, AGENT_FAMILY, "
                "PROJECT_PSEUDONYM, DECISION, CHILD_STARTED, ATTEMPTED_AT FROM "
                "INSTALL_ATTEMPTS WHERE ATTEMPT_ID={attempt_id}",
                {"attempt_id": attempt_id},
            )
        )
        return None if not rows else self._attempt(rows[0])

    def list_attempts(self, *, limit: int = 100) -> tuple[InstallAttempt, ...]:
        _validate_limit(limit)
        rows = _rows(
            self._connection.execute(
                "SELECT ATTEMPT_ID, DECISION_ID, MANAGER, ARGUMENTS_JSON, AGENT_FAMILY, "
                "PROJECT_PSEUDONYM, DECISION, CHILD_STARTED, ATTEMPTED_AT FROM "
                "INSTALL_ATTEMPTS ORDER BY ATTEMPTED_AT DESC, ATTEMPT_ID DESC LIMIT {limit!d}",
                {"limit": limit},
            )
        )
        return tuple(self._attempt(row) for row in rows)

    def create_intervention(self, intervention: Intervention) -> Intervention:
        parameters = {
            "intervention_id": intervention.intervention_id,
            "decision_id": intervention.decision.decision_id,
            "request_json": _json(_request_payload(intervention.request)),
            "decision_json": _json(_decision_payload(intervention.decision)),
            "evidence_labels_json": _json(list(intervention.evidence_labels)),
            "status": intervention.status.value,
            "created_at": _exasol_timestamp(intervention.created_at),
            "approval_id": intervention.approval_id,
        }
        for retry in range(5):
            try:
                self._connection.execute(
                    "INSERT INTO INTERVENTIONS (INTERVENTION_ID, DECISION_ID, REQUEST_JSON, "
                    "DECISION_JSON, EVIDENCE_LABELS_JSON, STATUS, CREATED_AT, APPROVAL_ID) "
                    "VALUES ({intervention_id}, {decision_id}, {request_json}, "
                    "{decision_json}, {evidence_labels_json}, {status}, {created_at}, "
                    "{approval_id})",
                    parameters,
                )
                self._connection.commit()
                return intervention
            except Exception:
                self._connection.rollback()
                try:
                    existing = self.get_intervention(intervention.intervention_id)
                except KeyError:
                    if retry < 4:
                        sleep(0.02 * (retry + 1))
                    continue
                if existing == intervention:
                    return existing
                break
        raise RuntimeError("intervention could not be persisted after transaction collisions")

    @staticmethod
    def _intervention(row: Sequence[Any]) -> Intervention:
        return Intervention(
            intervention_id=str(row[0]),
            request=_request_from_json(str(row[1])),
            decision=_decision_from_json(str(row[2])),
            evidence_labels=tuple(str(label) for label in json.loads(str(row[3]))),
            status=InterventionStatus(str(row[4])),
            created_at=_utc_timestamp(row[5]),
            approval_id=None if row[6] is None else str(row[6]),
        )

    def list_interventions(
        self, *, pending_only: bool = False, limit: int = 100
    ) -> tuple[Intervention, ...]:
        _validate_limit(limit)
        if pending_only:
            sql = (
                "SELECT INTERVENTION_ID, REQUEST_JSON, DECISION_JSON, EVIDENCE_LABELS_JSON, "
                "STATUS, CREATED_AT, APPROVAL_ID FROM INTERVENTIONS "
                "WHERE STATUS={pending_status} ORDER BY CREATED_AT DESC, "
                "INTERVENTION_ID DESC LIMIT {limit!d}"
            )
            parameters: dict[str, object] = {
                "limit": limit,
                "pending_status": InterventionStatus.PENDING.value,
            }
        else:
            sql = (
                "SELECT INTERVENTION_ID, REQUEST_JSON, DECISION_JSON, EVIDENCE_LABELS_JSON, "
                "STATUS, CREATED_AT, APPROVAL_ID FROM INTERVENTIONS "
                "ORDER BY CREATED_AT DESC, INTERVENTION_ID DESC LIMIT {limit!d}"
            )
            parameters = {"limit": limit}
        rows = _rows(
            self._connection.execute(sql, parameters)
        )
        return tuple(self._intervention(row) for row in rows)

    def get_intervention(self, intervention_id: str) -> Intervention:
        rows = _rows(
            self._connection.execute(
                "SELECT INTERVENTION_ID, REQUEST_JSON, DECISION_JSON, EVIDENCE_LABELS_JSON, "
                "STATUS, CREATED_AT, APPROVAL_ID FROM INTERVENTIONS "
                "WHERE INTERVENTION_ID={intervention_id}",
                {"intervention_id": intervention_id},
            )
        )
        if not rows:
            raise KeyError("intervention not found")
        return self._intervention(rows[0])

    def resolve_intervention(
        self,
        intervention_id: str,
        status: InterventionStatus,
        *,
        approval_id: str | None = None,
        resolved_at: datetime,
    ) -> Intervention:
        if status is InterventionStatus.PENDING:
            raise ValueError("resolved intervention cannot be pending")
        parameters = {
            "intervention_id": intervention_id,
            "status": status.value,
            "approval_id": approval_id,
            "resolved_at": _exasol_timestamp(resolved_at),
            "pending_status": InterventionStatus.PENDING.value,
        }
        try:
            result = self._connection.execute(
                "UPDATE INTERVENTIONS SET STATUS={status}, APPROVAL_ID={approval_id}, "
                "RESOLVED_AT={resolved_at} WHERE INTERVENTION_ID={intervention_id} "
                "AND STATUS={pending_status}",
                parameters,
            )
            if _affected_rows(result) != 1:
                self._connection.rollback()
                existing = self.get_intervention(intervention_id)
                if existing.status is status and existing.approval_id == approval_id:
                    return existing
                raise KeyError("pending intervention not found")
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        return self.get_intervention(intervention_id)

    def get_idempotency(self, idempotency_key: str) -> IdempotencyClaim | None:
        rows = _rows(
            self._connection.execute(
                "SELECT REQUEST_HASH, RESPONSE_REFERENCE, CREATED_AT FROM IDEMPOTENCY_CLAIMS "
                "WHERE IDEMPOTENCY_KEY={idempotency_key}",
                {"idempotency_key": idempotency_key},
            )
        )
        if not rows:
            return None
        row = rows[0]
        return IdempotencyClaim(
            idempotency_key=idempotency_key,
            request_hash=str(row[0]),
            response_reference=str(row[1]),
            created_at=_utc_timestamp(row[2]),
        )

    def claim_idempotency(
        self, idempotency_key: str, request_hash: str, response_reference: str
    ) -> IdempotencyClaim:
        existing = self.get_idempotency(idempotency_key)
        if existing is not None:
            if existing.request_hash != request_hash:
                self._connection.rollback()
                raise IdempotencyConflict("idempotency key was already used for another request")
            self._connection.commit()
            return existing
        created_at = datetime.now(UTC)
        parameters = {
            "idempotency_key": idempotency_key,
            "request_hash": request_hash,
            "response_reference": response_reference,
            "created_at": _exasol_timestamp(created_at),
        }
        try:
            self._connection.execute(
                "INSERT INTO IDEMPOTENCY_CLAIMS (IDEMPOTENCY_KEY, REQUEST_HASH, "
                "RESPONSE_REFERENCE, CREATED_AT) VALUES ({idempotency_key}, {request_hash}, "
                "{response_reference}, {created_at})",
                parameters,
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raced = self.get_idempotency(idempotency_key)
            if raced is not None:
                if raced.request_hash != request_hash:
                    raise IdempotencyConflict(
                        "idempotency key was already used for another request"
                    ) from None
                return raced
            raise
        return IdempotencyClaim(
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            response_reference=response_reference,
            created_at=created_at,
        )

    def consume_approval_nonce(
        self,
        approval_id: str,
        nonce: str,
        request_id: str,
        *,
        consumed_at: datetime,
        metadata: Mapping[str, Any],
    ) -> None:
        parameters = {
            "approval_id": approval_id,
            "nonce": nonce,
            "request_id": request_id,
            "consumed_at": _exasol_timestamp(consumed_at),
            "metadata_json": _json(dict(metadata)),
        }
        try:
            result = self._connection.execute(
                "UPDATE APPROVAL_GRANTS SET CONSUMED_AT={consumed_at}, "
                "CONSUMED_REQUEST_ID={request_id}, "
                "CONSUMPTION_METADATA_JSON={metadata_json} WHERE APPROVAL_ID={approval_id} "
                "AND NONCE={nonce} AND REQUEST_ID={request_id} "
                "AND EXPIRES_AT>{consumed_at} AND CONSUMED_AT IS NULL",
                parameters,
            )
            if _affected_rows(result) != 1:
                raise ApprovalNonceConflict("approval nonce is invalid or already consumed")
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def append_event(
        self,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        occurred_at: datetime,
    ) -> OperationalEvent:
        event_key = uuid4().hex
        try:
            parameters = {
                "event_key": event_key,
                "event_type": event_type,
                "payload_json": _json(dict(payload)),
                "occurred_at": _exasol_timestamp(occurred_at),
            }
            self._connection.execute(
                "INSERT INTO EVENT_LOG (EVENT_KEY, EVENT_TYPE, PAYLOAD_JSON, OCCURRED_AT) "
                "VALUES ({event_key}, {event_type}, {payload_json}, {occurred_at})",
                parameters,
            )
            event_rows = _rows(
                self._connection.execute(
                    "SELECT EVENT_ID FROM EVENT_LOG WHERE EVENT_KEY={event_key}",
                    {"event_key": event_key},
                )
            )
            if not event_rows:
                raise RuntimeError("persisted event identity was not returned")
            event_id = int(event_rows[0][0])
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        return OperationalEvent(
            event_id=event_id,
            event_type=event_type,
            payload=MappingProxyType(dict(payload)),
            occurred_at=_utc_timestamp(occurred_at),
        )

    def events_after(
        self, *, after_id: int = 0, limit: int = 100
    ) -> tuple[OperationalEvent, ...]:
        _validate_limit(limit)
        rows = _rows(
            self._connection.execute(
                "SELECT EVENT_ID, EVENT_TYPE, PAYLOAD_JSON, OCCURRED_AT FROM EVENT_LOG "
                "WHERE EVENT_ID>{after_id} ORDER BY EVENT_ID ASC LIMIT {limit!d}",
                {"after_id": max(after_id, 0), "limit": limit},
            )
        )
        return tuple(
            OperationalEvent(
                event_id=int(row[0]),
                event_type=str(row[1]),
                payload=MappingProxyType(dict(json.loads(str(row[2])))),
                occurred_at=_utc_timestamp(row[3]),
            )
            for row in rows
        )


class ExasolDemoRepository:
    """Fixture-scoped reset/replay operations; never deletes unrelated intelligence."""

    def __init__(self, connection: ExasolConnection) -> None:
        self._connection = connection

    @staticmethod
    def _identity_parameters(fixture: FixedDemoFixture) -> dict[str, object]:
        return {
            "ecosystem": fixture.package.ecosystem.value,
            "registry_origin": fixture.package.registry_origin,
            "canonical_name": fixture.package.canonical_name,
            "demo_prefix": "demo-%",
        }

    def _delete_identity_rows(self, fixture: FixedDemoFixture) -> None:
        parameters = self._identity_parameters(fixture)
        identity_tables = (
            "PUBLIC_SOURCE_OBSERVATIONS",
            "CLIENT_INSTALL_OBSERVATIONS",
            "PACKAGE_RELEASES",
            "REGISTRY_CHECKS",
            "PACKAGE_MENTIONS",
            "CANDIDATES",
        )
        for table in identity_tables:
            self._connection.execute(
                f"DELETE FROM {table} WHERE ECOSYSTEM={{ecosystem}} "  # noqa: S608
                "AND REGISTRY_ORIGIN={registry_origin} AND CANONICAL_NAME={canonical_name}",
                parameters,
            )

    def reset(self, fixture: FixedDemoFixture) -> None:
        parameters = self._identity_parameters(fixture)
        try:
            self._connection.execute(
                "DELETE FROM INSTALL_ATTEMPTS WHERE DECISION_ID IN ("
                "SELECT DECISION_ID FROM POLICY_DECISIONS WHERE ECOSYSTEM={ecosystem} "
                "AND REGISTRY_ORIGIN={registry_origin} AND CANONICAL_NAME={canonical_name})",
                parameters,
            )
            self._connection.execute(
                "DELETE FROM EVIDENCE_ATTESTATIONS WHERE DECISION_ID IN ("
                "SELECT DECISION_ID FROM POLICY_DECISIONS WHERE ECOSYSTEM={ecosystem} "
                "AND REGISTRY_ORIGIN={registry_origin} AND CANONICAL_NAME={canonical_name})",
                parameters,
            )
            self._connection.execute(
                "DELETE FROM POLICY_DECISIONS WHERE ECOSYSTEM={ecosystem} "
                "AND REGISTRY_ORIGIN={registry_origin} AND CANONICAL_NAME={canonical_name}",
                parameters,
            )
            self._connection.execute(
                "DELETE FROM APPROVAL_GRANTS WHERE APPROVAL_ID LIKE {demo_prefix}", parameters
            )
            self._delete_identity_rows(fixture)
            self._connection.execute(
                "DELETE FROM MODEL_RUNS WHERE RUN_ID LIKE {demo_prefix}", parameters
            )
            self._connection.execute(
                "DELETE FROM MODEL_CONFIGURATIONS WHERE CONFIGURATION_ID LIKE {demo_prefix}",
                parameters,
            )
            self._connection.execute(
                "DELETE FROM PROMPT_TASKS WHERE PROMPT_TASK_ID LIKE {demo_prefix}", parameters
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def replay_global_evidence(self, fixture: FixedDemoFixture) -> None:
        identity = self._identity_parameters(fixture)
        try:
            self._delete_identity_rows(fixture)
            self._connection.execute(
                "INSERT INTO CANDIDATES (ECOSYSTEM, REGISTRY_ORIGIN, CANONICAL_NAME, STATUS, "
                "FIRST_ABSENCE_AT, FIRST_REGISTRATION_AT, DISCLOSURE_CLASS, SYNTHETIC) VALUES "
                "({ecosystem}, {registry_origin}, {canonical_name}, 'verified_hallucination', "
                "{first_absence_at}, NULL, 'restricted_target_intelligence', TRUE)",
                {**identity, "first_absence_at": _exasol_timestamp(fixture.first_absence_at)},
            )
            self._connection.execute(
                "INSERT INTO REGISTRY_CHECKS (CHECK_ID, ECOSYSTEM, REGISTRY_ORIGIN, "
                "CANONICAL_NAME, ENDPOINT, STATUS, HTTP_STATUS, CHECKED_AT, RESPONSE_SHA256, "
                "ERROR_CLASS) VALUES ({check_id}, {ecosystem}, {registry_origin}, "
                "{canonical_name}, {endpoint}, 'absent', 404, {checked_at}, "
                "{response_sha256}, NULL)",
                {
                    **identity,
                    "check_id": "demo-absence-check",
                    "endpoint": (
                        f"{fixture.package.registry_origin}/"
                        f"{quote(fixture.package.canonical_name, safe='@')}"
                    ),
                    "checked_at": _exasol_timestamp(fixture.first_absence_at),
                    "response_sha256": "a" * 64,
                },
            )
            self._insert_replay_sources(fixture, identity)
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def record_registration(self, fixture: FixedDemoFixture) -> None:
        """Append the fixture registration without mutating its historical absence evidence."""

        identity = self._identity_parameters(fixture)
        try:
            self._connection.execute(
                "UPDATE CANDIDATES SET STATUS='registered_after_absence', "
                "FIRST_REGISTRATION_AT={registered_at} WHERE ECOSYSTEM={ecosystem} "
                "AND REGISTRY_ORIGIN={registry_origin} AND CANONICAL_NAME={canonical_name}",
                {**identity, "registered_at": _exasol_timestamp(fixture.registered_at)},
            )
            self._connection.execute(
                "DELETE FROM REGISTRY_CHECKS WHERE CHECK_ID={check_id}",
                {"check_id": "demo-registration-check"},
            )
            self._connection.execute(
                "INSERT INTO REGISTRY_CHECKS (CHECK_ID, ECOSYSTEM, REGISTRY_ORIGIN, "
                "CANONICAL_NAME, ENDPOINT, STATUS, HTTP_STATUS, CHECKED_AT, RESPONSE_SHA256, "
                "ERROR_CLASS) VALUES ({check_id}, {ecosystem}, {registry_origin}, "
                "{canonical_name}, {endpoint}, 'registered', 200, {checked_at}, "
                "{response_sha256}, NULL)",
                {
                    **identity,
                    "check_id": "demo-registration-check",
                    "endpoint": (
                        f"{fixture.package.registry_origin}/"
                        f"{quote(fixture.package.canonical_name, safe='@')}"
                    ),
                    "checked_at": _exasol_timestamp(fixture.registered_at),
                    "response_sha256": "d" * 64,
                },
            )
            self._connection.execute(
                "DELETE FROM PACKAGE_RELEASES WHERE RELEASE_ID={release_id}",
                {"release_id": "demo-release-1.0.0"},
            )
            self._connection.execute(
                "INSERT INTO PACKAGE_RELEASES (RELEASE_ID, ECOSYSTEM, REGISTRY_ORIGIN, "
                "CANONICAL_NAME, VERSION, UPLOADED_AT, FIRST_SEEN_AT, ARTIFACT_SHA256) "
                "VALUES ({release_id}, {ecosystem}, {registry_origin}, {canonical_name}, "
                "'1.0.0', {registered_at}, {registered_at}, {artifact_sha256})",
                {
                    **identity,
                    "release_id": "demo-release-1.0.0",
                    "registered_at": _exasol_timestamp(fixture.registered_at),
                    "artifact_sha256": "b" * 64,
                },
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def _insert_replay_sources(
        self,
        fixture: FixedDemoFixture,
        identity: dict[str, object],
    ) -> None:
        for index in range(fixture.model_configurations):
            configuration_id = f"demo-model-{index}"
            self._connection.execute(
                "MERGE INTO MODEL_CONFIGURATIONS T USING (SELECT {configuration_id} "
                "CONFIGURATION_ID FROM DUAL) S ON T.CONFIGURATION_ID=S.CONFIGURATION_ID "
                "WHEN NOT MATCHED THEN INSERT (CONFIGURATION_ID, PROVIDER, MODEL_ID, "
                "PARAMETERS_JSON, FIRST_SEEN_AT, LAST_SEEN_AT) VALUES ({configuration_id}, "
                "'replay', {model_id}, {parameters_json}, {first_seen_at}, {last_seen_at})",
                {
                    "configuration_id": configuration_id,
                    "model_id": f"replay-model-{index}",
                    "parameters_json": "{}",
                    "first_seen_at": _exasol_timestamp(fixture.first_absence_at),
                    "last_seen_at": _exasol_timestamp(fixture.attack_at),
                },
            )
        self._connection.execute(
            "MERGE INTO PROMPT_TASKS T USING (SELECT {prompt_task_id} PROMPT_TASK_ID FROM DUAL) "
            "S ON T.PROMPT_TASK_ID=S.PROMPT_TASK_ID WHEN NOT MATCHED THEN INSERT "
            "(PROMPT_TASK_ID, SUITE_VERSION, CATEGORY, PROMPT_SHA256, EXPECTED_ECOSYSTEM) VALUES "
            "({prompt_task_id}, {suite_version}, 'package_install', {prompt_sha256}, 'npm')",
            {
                "prompt_task_id": "demo-prompt-package-install",
                "suite_version": fixture.fixture_version,
                "prompt_sha256": "b" * 64,
            },
        )
        for row in fixture.mention_rows():
            parameters = {
                **identity,
                **row,
                "observed_at": _exasol_timestamp(row["observed_at"]),
            }
            if row["provenance"] == "model_probe":
                self._connection.execute(
                    "MERGE INTO MODEL_RUNS T USING (SELECT {source_id} RUN_ID FROM DUAL) S "
                    "ON T.RUN_ID=S.RUN_ID WHEN NOT MATCHED THEN INSERT (RUN_ID, "
                    "CONFIGURATION_ID, PROMPT_TASK_ID, RUN_AT, RESPONSE_SHA256, STATUS) VALUES "
                    "({source_id}, {model_configuration_id}, 'demo-prompt-package-install', "
                    "{observed_at}, {response_sha256}, 'replayed_synthetic')",
                    {**parameters, "response_sha256": "c" * 64},
                )
            elif row["provenance"] == "agent_install_attempt":
                self._connection.execute(
                    "INSERT INTO CLIENT_INSTALL_OBSERVATIONS (OBSERVATION_ID, ECOSYSTEM, "
                    "REGISTRY_ORIGIN, CANONICAL_NAME, CLIENT_PSEUDONYM, AGENT_FAMILY, "
                    "REQUESTED_SOURCE, OBSERVED_AT) VALUES ({mention_id}, {ecosystem}, "
                    "{registry_origin}, {canonical_name}, {source_id}, 'codex', 'registry', "
                    "{observed_at})",
                    parameters,
                )
            elif row["provenance"] == "public_ci_failure":
                self._connection.execute(
                    "INSERT INTO PUBLIC_SOURCE_OBSERVATIONS (OBSERVATION_ID, ECOSYSTEM, "
                    "REGISTRY_ORIGIN, CANONICAL_NAME, PUBLIC_URL_SHA256, SOURCE_KIND, "
                    "REMOVAL_STATE, OBSERVED_AT) VALUES ({mention_id}, {ecosystem}, "
                    "{registry_origin}, {canonical_name}, {public_url_sha256}, 'ci_failure', "
                    "'present', {observed_at})",
                    {**parameters, "public_url_sha256": "d" * 64},
                )
            self._connection.execute(
                "INSERT INTO PACKAGE_MENTIONS (MENTION_ID, ECOSYSTEM, REGISTRY_ORIGIN, "
                "CANONICAL_NAME, PROVENANCE, SOURCE_ID, MODEL_CONFIGURATION_ID, OBSERVED_AT, "
                "CONTEXT_KIND, CONFIDENCE, EXPLICIT_CONTEXT) VALUES ({mention_id}, {ecosystem}, "
                "{registry_origin}, {canonical_name}, {provenance}, {source_id}, "
                "{model_configuration_id}, {observed_at}, {context_kind}, 1.0, TRUE)",
                parameters,
            )
