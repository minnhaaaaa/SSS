from __future__ import annotations

import hashlib
import json

from sss_core.domain import PolicyDecision


def canonical_decision_json(decision: PolicyDecision) -> bytes:
    document = {
        "decision": decision.decision.value,
        "decision_id": decision.decision_id,
        "expires_at": decision.expires_at.isoformat() if decision.expires_at else None,
        "policy_version": decision.policy_version,
        "reason_codes": list(decision.reason_codes),
        "request_id": decision.request_id,
        "scores": {
            "absence_confidence": decision.scores.absence_confidence,
            "package_policy_risk": decision.scores.package_policy_risk,
            "target_attractiveness": decision.scores.target_attractiveness,
        },
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode()


def attest_decision(decision: PolicyDecision) -> str:
    return hashlib.sha256(canonical_decision_json(decision)).hexdigest()
