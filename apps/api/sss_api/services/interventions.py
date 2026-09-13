"""Thread-safe pending intervention state for the local Guard service."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from threading import RLock

from sss_core import InstallRequest, PolicyDecision


class InterventionStatus(StrEnum):
    PENDING = "pending"
    KEPT_BLOCKED = "kept_blocked"
    APPROVED = "approved"


@dataclass(frozen=True, slots=True)
class Intervention:
    intervention_id: str
    request: InstallRequest
    decision: PolicyDecision
    evidence_labels: tuple[str, ...]
    status: InterventionStatus
    created_at: datetime
    approval_id: str | None = None


class InterventionStore:
    def __init__(self) -> None:
        self._items: dict[str, Intervention] = {}
        self._lock = RLock()

    def create(
        self,
        request: InstallRequest,
        decision: PolicyDecision,
        *,
        evidence_labels: tuple[str, ...],
    ) -> Intervention:
        with self._lock:
            existing = self._items.get(decision.decision_id)
            if existing is not None:
                return existing
            intervention = Intervention(
                intervention_id=decision.decision_id,
                request=request,
                decision=decision,
                evidence_labels=evidence_labels,
                status=InterventionStatus.PENDING,
                created_at=datetime.now(UTC),
            )
            self._items[intervention.intervention_id] = intervention
            return intervention

    def list_pending(self) -> tuple[Intervention, ...]:
        with self._lock:
            return tuple(
                item
                for item in self._items.values()
                if item.status is InterventionStatus.PENDING
            )

    def get(self, intervention_id: str) -> Intervention:
        with self._lock:
            try:
                return self._items[intervention_id]
            except KeyError as exc:
                raise KeyError("intervention not found") from exc

    def keep_blocked(self, intervention_id: str) -> Intervention:
        with self._lock:
            item = self.get(intervention_id)
            updated = replace(item, status=InterventionStatus.KEPT_BLOCKED)
            self._items[intervention_id] = updated
            return updated

    def resolve_approved(self, intervention_id: str, approval_id: str) -> Intervention:
        with self._lock:
            item = self.get(intervention_id)
            updated = replace(
                item,
                status=InterventionStatus.APPROVED,
                approval_id=approval_id,
            )
            self._items[intervention_id] = updated
            return updated
