from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

from sss_core.demo import FixedDemoFixture
from sss_core.domain import CandidateStatus, PackageIdentity, RegistryStatus


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
            "SELECT * FROM V_RADAR_PRIVATE WHERE ECOSYSTEM={ecosystem} "
            "AND REGISTRY_ORIGIN={origin} AND CANONICAL_NAME={name}",
            {"ecosystem": ecosystem, "origin": origin, "name": name},
        )
        rows = _rows(result)
        return {} if not rows else {str(index): value for index, value in enumerate(rows[0])}


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
                f"DELETE FROM {table} WHERE ECOSYSTEM={{ecosystem}} "
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
