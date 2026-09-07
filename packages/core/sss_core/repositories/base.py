from __future__ import annotations

from typing import Protocol

from sss_core.domain import CandidateStatus
from sss_core.repositories.exasol import RegistryEvidenceRecord


class EvidenceRepository(Protocol):
    def store_evidence_and_transition(
        self,
        evidence: RegistryEvidenceRecord,
        candidate_status: CandidateStatus,
    ) -> None: ...


class RadarRepository(Protocol):
    def list_private(self, *, limit: int = 100) -> list[dict[str, object]]: ...


class PolicyRepository(Protocol):
    def load_evidence(self, *, ecosystem: str, origin: str, name: str) -> dict[str, object]: ...
