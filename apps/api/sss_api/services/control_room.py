"""Read models for the browser control room backed by Exasol views."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sss_core.evidence.scoring import AttractivenessInputs, score_target_attractiveness
from sss_core.repositories.exasol import ExasolConnection, ExasolResult

from sss_api.schemas.observations import ClientObservation, ModelObservation, PublicObservation
from sss_api.services.attempts import AttemptStore
from sss_api.services.guard import GuardRecord, GuardService
from sss_api.services.observations import Observation, ObservationStore


def _rows(result: ExasolResult | Sequence[Sequence[Any]]) -> list[tuple[Any, ...]]:
    values = result.fetchall() if hasattr(result, "fetchall") else result
    return [tuple(row) for row in values]


def _number(value: object | None) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float, Decimal)):
        return int(value)
    return int(str(value))


def _instant(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return normalized.isoformat()
    return str(value)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _identity(ecosystem: str, origin: str, name: str) -> tuple[str, str, str]:
    return ecosystem, origin, name


def _identity_id(identity: tuple[str, str, str]) -> str:
    return hashlib.sha256("\0".join(identity).encode()).hexdigest()


@dataclass(slots=True)
class _RuntimePackage:
    ecosystem: str
    origin: str
    name: str
    observations: list[Observation] = field(default_factory=list)
    decisions: list[GuardRecord] = field(default_factory=list)


class RuntimeControlRoomService:
    """Build control-room views exclusively from activity accepted by this process."""

    def __init__(
        self,
        observations: ObservationStore,
        guard: GuardService,
        attempts: AttemptStore,
    ) -> None:
        self._observations = observations
        self._guard = guard
        self._attempts = attempts

    def packages(self) -> list[dict[str, object]]:
        values = [self._package_value(item) for item in self._facts().values()]
        return sorted(
            values,
            key=lambda item: (_number(item["attractiveness"]), str(item["last_seen"] or "")),
            reverse=True,
        )

    def package(self, name: str) -> dict[str, object] | None:
        item = next((value for value in self._facts().values() if value.name == name), None)
        if item is None:
            return None
        return {
            **self._package_value(item),
            "lifecycle": [event["label"] for event in self._evidence_values(item)],
        }

    def evidence(self, name: str) -> list[dict[str, object]]:
        items = [value for value in self._facts().values() if value.name == name]
        events = [event for item in items for event in self._evidence_values(item)]
        return sorted(events, key=lambda event: str(event["occurred_at"]), reverse=True)

    def decisions(self) -> list[dict[str, object]]:
        attempts = {attempt.decision_id: attempt for attempt in self._attempts.list_all()}
        return [
            self._decision_value(record, attempts.get(record.assessment.decision.decision_id))
            for record in self._guard.records()
        ]

    def coverage(self) -> dict[str, object]:
        observations = self._observations.list_all()
        records = self._guard.records()
        origins = sorted(
            {
                (item.package.ecosystem.value, item.package.registry_origin)
                for item in observations
            }
            | {
                (record.request.package.ecosystem.value, record.request.package.registry_origin)
                for record in records
            }
        )
        instants = [_utc(item.observed_at) for item in observations]
        instants.extend(record.decided_at for record in records)
        return {
            "data_as_of": (max(instants) if instants else datetime.now(UTC)).isoformat(),
            "registries": [
                {
                    "id": hashlib.sha256(f"{ecosystem}\0{origin}".encode()).hexdigest(),
                    "name": ecosystem,
                    "state": "unknown",
                    "detail": origin,
                }
                for ecosystem, origin in origins
            ],
            "services": [],
            "protected_agents": len(
                {
                    item.client_pseudonym
                    for item in observations
                    if isinstance(item, ClientObservation)
                }
            ),
            "observation_days": len({_utc(item.observed_at).date() for item in observations}),
            "verified_recommendations": len(
                {item.source_id for item in observations if isinstance(item, ModelObservation)}
            ),
            "public_failed_references": len(
                {
                    item.source_id
                    for item in observations
                    if isinstance(item, PublicObservation)
                    and item.provenance == "public_ci_failure"
                }
            ),
            "model_configurations": len(
                {
                    item.model_configuration_id
                    for item in observations
                    if isinstance(item, ModelObservation)
                }
            ),
        }

    def overview(self) -> dict[str, object]:
        packages = self.packages()
        decisions = self.decisions()
        coverage = self.coverage()
        return {
            "data_as_of": coverage["data_as_of"],
            "guard_status": "degraded",
            "active_threats": sum(
                1
                for item in packages
                if item["state"] == "high_risk"
                or (
                    item["state"] == "blocked"
                    and _number(item["policy_risk"]) >= 60
                )
            ),
            "protected_agents": coverage["protected_agents"],
            "verified_recommendations": coverage["verified_recommendations"],
            "radar_nodes": packages,
            "prioritized_targets": packages[:10],
            "recent_activity": [
                {
                    "id": item["id"],
                    "kind": item["result"],
                    "label": f"Guard decision: {str(item['result']).upper()}",
                    "package_name": item["package_name"],
                    "occurred_at": item["occurred_at"],
                }
                for item in decisions[:10]
            ],
        }

    def _facts(self) -> dict[tuple[str, str, str], _RuntimePackage]:
        facts: dict[tuple[str, str, str], _RuntimePackage] = {}
        for observation in self._observations.list_all():
            observed_package = observation.package
            key = _identity(
                observed_package.ecosystem.value,
                observed_package.registry_origin,
                observed_package.canonical_name,
            )
            facts.setdefault(key, _RuntimePackage(*key)).observations.append(observation)
        for record in self._guard.records():
            requested_package = record.request.package
            key = _identity(
                requested_package.ecosystem.value,
                requested_package.registry_origin,
                requested_package.canonical_name,
            )
            facts.setdefault(key, _RuntimePackage(*key)).decisions.append(record)
        return facts

    def _package_value(self, item: _RuntimePackage) -> dict[str, object]:
        latest = item.decisions[0] if item.decisions else None
        model_sources = {
            observation.source_id
            for observation in item.observations
            if isinstance(observation, ModelObservation)
        }
        model_configurations = {
            observation.model_configuration_id
            for observation in item.observations
            if isinstance(observation, ModelObservation)
        }
        clients = {
            observation.client_pseudonym
            for observation in item.observations
            if isinstance(observation, ClientObservation)
        }
        public_sources = {
            observation.source_id
            for observation in item.observations
            if isinstance(observation, PublicObservation)
        }
        days = {_utc(observation.observed_at).date() for observation in item.observations}
        attractiveness = score_target_attractiveness(
            AttractivenessInputs(
                distinct_verified_runs=len(model_sources),
                distinct_model_configurations=len(model_configurations),
                distinct_clients=len(clients),
                distinct_public_sources=len(public_sources),
                distinct_observation_days=len(days),
                explicit_install_context=any(
                    observation.explicit_install_context for observation in item.observations
                ),
            )
        )
        instants = [_utc(observation.observed_at) for observation in item.observations]
        instants.extend(record.decided_at for record in item.decisions)
        decision = latest.assessment.decision if latest is not None else None
        state = "monitored"
        if decision is not None and decision.decision.value == "block":
            state = "blocked"
        elif decision is not None and decision.decision.value == "review":
            state = "high_risk"
        return {
            "id": _identity_id(_identity(item.ecosystem, item.origin, item.name)),
            "name": item.name,
            "ecosystem": item.ecosystem,
            "state": state,
            "attractiveness": attractiveness,
            "policy_risk": decision.scores.package_policy_risk if decision is not None else None,
            "last_seen": max(instants).isoformat() if instants else None,
            "absence_confidence": (
                decision.scores.absence_confidence if decision is not None else None
            ),
        }

    def _evidence_values(self, item: _RuntimePackage) -> list[dict[str, object]]:
        events: list[dict[str, object]] = [
            {
                "id": observation.observation_id,
                "type": observation.provenance,
                "label": observation.evidence_label,
                "provenance": observation.provenance,
                "occurred_at": _utc(observation.observed_at).isoformat(),
            }
            for observation in item.observations
        ]
        events.extend(
            {
                "id": record.assessment.decision.decision_id,
                "type": "guard_decision",
                "label": f"Guard decision: {record.assessment.decision.decision.value.upper()}",
                "provenance": "sss_guard",
                "occurred_at": record.decided_at.isoformat(),
            }
            for record in item.decisions
        )
        return events

    @staticmethod
    def _decision_value(record: GuardRecord, attempt: object | None) -> dict[str, object]:
        decision = record.assessment.decision
        child_started = getattr(attempt, "child_started", None)
        return {
            "id": decision.decision_id,
            "package_name": record.request.package.canonical_name,
            "ecosystem": record.request.package.ecosystem.value,
            "result": decision.decision.value,
            "policy": decision.policy_version,
            "occurred_at": record.decided_at.isoformat(),
            "reason_codes": list(decision.reason_codes),
            "package_manager_started": child_started,
            "package_code_executed": None,
        }


class ExasolControlRoomService:
    def __init__(self, connection: ExasolConnection) -> None:
        self._connection = connection

    def packages(self) -> list[dict[str, object]]:
        rows = _rows(
            self._connection.execute(
                "SELECT ECOSYSTEM, REGISTRY_ORIGIN, CANONICAL_NAME, STATUS, FIRST_ABSENCE_AT, "
                "FIRST_REGISTRATION_AT, VERIFIED_MODEL_RECOMMENDATIONS, MODEL_CONFIGURATIONS, "
                "PROTECTED_AGENT_ATTEMPTS, PUBLIC_FAILED_REFERENCES, OBSERVATION_DAYS, "
                "HAS_EXPLICIT_CONTEXT FROM V_RADAR_PRIVATE "
                "ORDER BY VERIFIED_MODEL_RECOMMENDATIONS DESC LIMIT 500"
            )
        )
        latest = self._latest_decisions()
        packages: list[dict[str, object]] = []
        for row in rows:
            ecosystem, origin, name, candidate_status = map(str, row[:4])
            attractiveness = score_target_attractiveness(
                AttractivenessInputs(
                    distinct_verified_runs=_number(row[6]),
                    distinct_model_configurations=_number(row[7]),
                    distinct_clients=_number(row[8]),
                    distinct_public_sources=_number(row[9]),
                    distinct_observation_days=_number(row[10]),
                    explicit_install_context=bool(row[11]),
                )
            )
            decision = latest.get((ecosystem, origin, name))
            state = self._state(candidate_status, attractiveness, decision)
            identity = f"{ecosystem}\0{origin}\0{name}".encode()
            packages.append(
                {
                    "id": hashlib.sha256(identity).hexdigest(),
                    "name": name,
                    "ecosystem": ecosystem,
                    "state": state,
                    "attractiveness": attractiveness,
                    "policy_risk": decision[1] if decision is not None else None,
                    "last_seen": _instant(row[5] or row[4]),
                    "absence_confidence": 100
                    if candidate_status
                    in {"verified_absent", "verified_hallucination", "registered_after_absence"}
                    else None,
                }
            )
        return packages

    def package(self, name: str) -> dict[str, object] | None:
        found = next((item for item in self.packages() if item["name"] == name), None)
        if found is None:
            return None
        lifecycle = [item["label"] for item in self.evidence(name)]
        return {**found, "lifecycle": lifecycle}

    def evidence(self, name: str) -> list[dict[str, object]]:
        rows = _rows(
            self._connection.execute(
                "SELECT EVENT_ID, EVENT_KIND, EVENT_AT, ECOSYSTEM FROM "
                "V_PACKAGE_EVIDENCE_TIMELINE WHERE CANONICAL_NAME={name} "
                "ORDER BY EVENT_AT DESC LIMIT 200",
                {"name": name},
            )
        )
        return [
            {
                "id": str(row[0]),
                "type": str(row[1]),
                "label": self._evidence_label(str(row[1])),
                "provenance": str(row[3]),
                "occurred_at": _instant(row[2]),
            }
            for row in rows
        ]

    def decisions(self) -> list[dict[str, object]]:
        rows = _rows(
            self._connection.execute(
                "SELECT D.DECISION_ID, D.CANONICAL_NAME, D.ECOSYSTEM, D.DECISION, "
                "D.POLICY_VERSION, D.DECIDED_AT, D.REASON_CODES_JSON, "
                "MAX(CASE WHEN A.CHILD_STARTED THEN 1 ELSE 0 END), COUNT(A.ATTEMPT_ID) "
                "FROM POLICY_DECISIONS D LEFT JOIN INSTALL_ATTEMPTS A "
                "ON A.DECISION_ID=D.DECISION_ID GROUP BY D.DECISION_ID, D.CANONICAL_NAME, "
                "D.ECOSYSTEM, D.DECISION, D.POLICY_VERSION, D.DECIDED_AT, "
                "D.REASON_CODES_JSON ORDER BY D.DECIDED_AT DESC LIMIT 500"
            )
        )
        return [
            {
                "id": str(row[0]),
                "package_name": str(row[1]),
                "ecosystem": str(row[2]),
                "result": str(row[3]),
                "policy": str(row[4]),
                "occurred_at": _instant(row[5]),
                "reason_codes": self._reason_codes(row[6]),
                "package_manager_started": bool(row[7]) if _number(row[8]) > 0 else None,
                "package_code_executed": None,
            }
            for row in rows
        ]

    def coverage(self) -> dict[str, object]:
        row = _rows(
            self._connection.execute(
                "SELECT (SELECT COUNT(DISTINCT CLIENT_PSEUDONYM) "
                "FROM CLIENT_INSTALL_OBSERVATIONS), "
                "(SELECT COUNT(DISTINCT CAST(OBSERVED_AT AS DATE)) "
                "FROM PACKAGE_MENTIONS) FROM DUAL"
            )
        )[0]
        aggregate = _rows(
            self._connection.execute(
                "SELECT COUNT(DISTINCT CASE WHEN PROVENANCE='model_probe' THEN SOURCE_ID END), "
                "COUNT(DISTINCT CASE WHEN PROVENANCE IN ('public_ci_failure', "
                "'public_manifest') THEN SOURCE_ID END), "
                "COUNT(DISTINCT MODEL_CONFIGURATION_ID) FROM PACKAGE_MENTIONS"
            )
        )[0]
        origins = _rows(
            self._connection.execute(
                "SELECT DISTINCT ECOSYSTEM, REGISTRY_ORIGIN FROM CANDIDATES ORDER BY ECOSYSTEM"
            )
        )
        return {
            "data_as_of": datetime.now(UTC).isoformat(),
            "registries": [
                {
                    "id": hashlib.sha256(f"{item[0]}\0{item[1]}".encode()).hexdigest(),
                    "name": str(item[0]),
                    "state": "unknown",
                    "detail": str(item[1]),
                }
                for item in origins
            ],
            "services": [
                {
                    "id": "service-guard",
                    "name": "SSS Guard",
                    "state": "operational",
                    "detail": "Deterministic policy and Exasol evidence are connected",
                }
            ],
            "protected_agents": _number(row[0]),
            "observation_days": _number(row[1]),
            "verified_recommendations": _number(aggregate[0]),
            "public_failed_references": _number(aggregate[1]),
            "model_configurations": _number(aggregate[2]),
        }

    def overview(self) -> dict[str, object]:
        packages = self.packages()
        decisions = self.decisions()
        coverage = self.coverage()
        targets = sorted(packages, key=lambda item: _number(item["attractiveness"]), reverse=True)
        recent = [
            {
                "id": item["id"],
                "kind": item["result"],
                "label": f"Guard decision: {str(item['result']).upper()}",
                "package_name": item["package_name"],
                "occurred_at": item["occurred_at"],
            }
            for item in decisions[:10]
        ]
        return {
            "data_as_of": coverage["data_as_of"],
            "guard_status": "operational",
            "active_threats": sum(
                1 for item in packages if item["state"] in {"high_risk", "blocked"}
            ),
            "protected_agents": coverage["protected_agents"],
            "verified_recommendations": coverage["verified_recommendations"],
            "radar_nodes": packages,
            "prioritized_targets": targets[:10],
            "recent_activity": recent,
        }

    def _latest_decisions(self) -> dict[tuple[str, str, str], tuple[str, int]]:
        rows = _rows(
            self._connection.execute(
                "SELECT ECOSYSTEM, REGISTRY_ORIGIN, CANONICAL_NAME, DECISION, "
                "PACKAGE_POLICY_RISK FROM POLICY_DECISIONS ORDER BY DECIDED_AT DESC"
            )
        )
        latest: dict[tuple[str, str, str], tuple[str, int]] = {}
        for row in rows:
            key = (str(row[0]), str(row[1]), str(row[2]))
            latest.setdefault(key, (str(row[3]), _number(row[4])))
        return latest

    @staticmethod
    def _state(
        candidate_status: str,
        attractiveness: int,
        decision: tuple[str, int] | None,
    ) -> str:
        if decision is not None and decision[0] == "block":
            return "blocked"
        if candidate_status == "verified_absent":
            return "absent"
        if candidate_status == "registered":
            return "registered"
        if candidate_status in {"verified_hallucination", "registered_after_absence"}:
            return "high_risk" if attractiveness >= 60 else "monitored"
        return "monitored"

    @staticmethod
    def _evidence_label(kind: str) -> str:
        return {
            "absent": "Registry absence verified",
            "registered": "Registry presence verified",
            "release": "Package release observed",
            "model_probe": "Model recommendation observed",
            "agent_install_attempt": "Protected-agent install observed",
            "public_ci_failure": "Public CI failure observed",
            "public_manifest": "Public manifest reference observed",
        }.get(kind, kind.replace("_", " ").capitalize())

    @staticmethod
    def _reason_codes(value: object) -> list[str]:
        try:
            decoded = json.loads(str(value))
        except json.JSONDecodeError:
            return []
        return [str(item) for item in decoded] if isinstance(decoded, list) else []
