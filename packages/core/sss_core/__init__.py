"""Stable public domain and policy primitives for SSS consumers."""

from sss_core.auth import (
    CredentialAuditRecord,
    CredentialPrincipal,
    CredentialRecord,
    CredentialStore,
)
from sss_core.domain import (
    CandidateStatus,
    Decision,
    Ecosystem,
    EvidenceProvenance,
    EvidenceScores,
    InstallRequest,
    PackageIdentity,
    PolicyDecision,
    RegistryStatus,
)
from sss_core.policy.engine import POLICY_VERSION, PolicyContext, PolicyEngine
from sss_core.policy.reasons import ReasonCode
from sss_core.runtime import RuntimeMode

__all__ = [
    "POLICY_VERSION",
    "CandidateStatus",
    "CredentialAuditRecord",
    "CredentialPrincipal",
    "CredentialRecord",
    "CredentialStore",
    "Decision",
    "Ecosystem",
    "EvidenceProvenance",
    "EvidenceScores",
    "InstallRequest",
    "PackageIdentity",
    "PolicyContext",
    "PolicyDecision",
    "PolicyEngine",
    "ReasonCode",
    "RegistryStatus",
    "RuntimeMode",
]
