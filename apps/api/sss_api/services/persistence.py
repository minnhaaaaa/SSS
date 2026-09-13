"""Exasol persistence adapters for enforcement outcomes."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC

from sss_core import InstallRequest, PolicyDecision
from sss_core.repositories.exasol import ExasolConnection

from sss_api.services.attempts import InstallAttempt


class ExasolDecisionSink:
    def __init__(self, connection: ExasolConnection) -> None:
        self._connection = connection

    def store(self, request: InstallRequest, decision: PolicyDecision) -> None:
        parameters = {
            "decision_id": decision.decision_id,
            "request_id": request.request_id,
            "ecosystem": request.package.ecosystem.value,
            "registry_origin": request.package.registry_origin,
            "canonical_name": request.package.canonical_name,
            "absence_confidence": decision.scores.absence_confidence,
            "target_attractiveness": decision.scores.target_attractiveness,
            "package_policy_risk": decision.scores.package_policy_risk,
            "decision": decision.decision.value,
            "reason_codes_json": json.dumps(decision.reason_codes, separators=(",", ":")),
            "policy_version": decision.policy_version,
        }
        try:
            self._connection.execute(
                "MERGE INTO POLICY_DECISIONS T USING (SELECT {decision_id} DECISION_ID "
                "FROM DUAL) S ON T.DECISION_ID=S.DECISION_ID WHEN NOT MATCHED THEN INSERT "
                "(DECISION_ID, REQUEST_ID, ECOSYSTEM, REGISTRY_ORIGIN, CANONICAL_NAME, "
                "ABSENCE_CONFIDENCE, TARGET_ATTRACTIVENESS, PACKAGE_POLICY_RISK, DECISION, "
                "REASON_CODES_JSON, POLICY_VERSION, DECIDED_AT) VALUES ({decision_id}, "
                "{request_id}, {ecosystem}, {registry_origin}, {canonical_name}, "
                "{absence_confidence}, {target_attractiveness}, {package_policy_risk}, "
                "{decision}, {reason_codes_json}, {policy_version}, CURRENT_TIMESTAMP)",
                parameters,
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise


class ExasolAttemptSink:
    def __init__(self, connection: ExasolConnection) -> None:
        self._connection = connection

    def store(self, attempt: InstallAttempt) -> None:
        command = json.dumps(
            [attempt.manager, *attempt.arguments], separators=(",", ":"), ensure_ascii=True
        )
        attempt_id = hashlib.sha256(
            f"{attempt.decision_id}\0{command}\0{attempt.attempted_at.isoformat()}".encode()
        ).hexdigest()
        parameters = {
            "attempt_id": attempt_id,
            "decision_id": attempt.decision_id,
            "command_sha256": hashlib.sha256(command.encode()).hexdigest(),
            "agent_family": attempt.agent_family,
            "project_pseudonym": hashlib.sha256(attempt.project_id.encode()).hexdigest(),
            "decision": attempt.decision.value,
            "child_started": attempt.child_started,
            "attempted_at": attempt.attempted_at.astimezone(UTC).replace(tzinfo=None),
        }
        try:
            self._connection.execute(
                "MERGE INTO INSTALL_ATTEMPTS T USING (SELECT {attempt_id} ATTEMPT_ID FROM DUAL) "
                "S ON T.ATTEMPT_ID=S.ATTEMPT_ID WHEN NOT MATCHED THEN INSERT (ATTEMPT_ID, "
                "DECISION_ID, COMMAND_SHA256, AGENT_FAMILY, PROJECT_PSEUDONYM, DECISION, "
                "CHILD_STARTED, ATTEMPTED_AT) VALUES ({attempt_id}, {decision_id}, "
                "{command_sha256}, {agent_family}, {project_pseudonym}, {decision}, "
                "{child_started}, {attempted_at})",
                parameters,
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
