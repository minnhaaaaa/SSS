from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Ecosystem(StrEnum):
    PYPI = "pypi"
    NPM = "npm"


class EvidenceProvenance(StrEnum):
    MODEL_PROBE = "model_probe"
    AGENT_INSTALL_ATTEMPT = "agent_install_attempt"
    PUBLIC_MANIFEST = "public_manifest"
    PUBLIC_CI_FAILURE = "public_ci_failure"
    USER_REPORT = "user_report"


class RegistryStatus(StrEnum):
    REGISTERED = "registered"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class CandidateStatus(StrEnum):
    AMBIGUOUS = "ambiguous"
    VERIFIED_ABSENT = "verified_absent"
    VERIFIED_HALLUCINATION = "verified_hallucination"
    REGISTERED = "registered"
    REGISTERED_AFTER_ABSENCE = "registered_after_absence"


class Decision(StrEnum):
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"


@dataclass(frozen=True)
class PackageIdentity:
    ecosystem: Ecosystem
    registry_origin: str
    canonical_name: str


@dataclass(frozen=True)
class InstallRequest:
    request_id: str
    project_id: str
    agent_family: str
    package: PackageIdentity
    version_spec: str | None
    direct_url: str | None
    artifact_sha256: str | None
    is_direct: bool


@dataclass(frozen=True)
class EvidenceScores:
    absence_confidence: int | None
    target_attractiveness: int
    package_policy_risk: int


@dataclass(frozen=True)
class PolicyDecision:
    decision_id: str
    request_id: str
    decision: Decision
    reason_codes: tuple[str, ...]
    scores: EvidenceScores
    policy_version: str
    expires_at: datetime | None
