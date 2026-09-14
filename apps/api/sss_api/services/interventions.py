"""Thread-safe pending intervention state for the local Guard service."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from threading import RLock

from sss_core import InstallRequest, PolicyDecision
from sss_core.repositories.operations import (
    Intervention,
    InterventionStatus,
    OperationalRepository,
)

__all__ = ["Intervention", "InterventionStatus", "InterventionStore"]


class InterventionStore:
    def __init__(self, repository: OperationalRepository | None = None) -> None:
        self._items: dict[str, Intervention] = {}
        self._lock = RLock()
        self._repository = repository

    def create(
        self,
        request: InstallRequest,
        decision: PolicyDecision,
        *,
        evidence_labels: tuple[str, ...],
        created_at: datetime | None = None,
    ) -> Intervention:
        if self._repository is not None:
            try:
                return self._repository.get_intervention(decision.decision_id)
            except KeyError:
                pass
            intervention = Intervention(
                intervention_id=decision.decision_id,
                request=request,
                decision=decision,
                evidence_labels=evidence_labels,
                status=InterventionStatus.PENDING,
                created_at=datetime.now(UTC) if created_at is None else created_at,
            )
            return self._repository.create_intervention(intervention)
        with self._lock:
            existing_intervention = self._items.get(decision.decision_id)
            if existing_intervention is not None:
                return existing_intervention
            intervention = Intervention(
                intervention_id=decision.decision_id,
                request=request,
                decision=decision,
                evidence_labels=evidence_labels,
                status=InterventionStatus.PENDING,
                created_at=datetime.now(UTC) if created_at is None else created_at,
            )
            self._items[intervention.intervention_id] = intervention
            return intervention

    def list_pending(self) -> tuple[Intervention, ...]:
        if self._repository is not None:
            return self._repository.list_interventions(pending_only=True, limit=1000)
        with self._lock:
            return tuple(
                item
                for item in self._items.values()
                if item.status is InterventionStatus.PENDING
            )

    def get(self, intervention_id: str) -> Intervention:
        if self._repository is not None:
            return self._repository.get_intervention(intervention_id)
        with self._lock:
            try:
                return self._items[intervention_id]
            except KeyError as exc:
                raise KeyError("intervention not found") from exc

    def keep_blocked(
        self, intervention_id: str, *, resolved_at: datetime | None = None
    ) -> Intervention:
        if self._repository is not None:
            return self._repository.resolve_intervention(
                intervention_id,
                InterventionStatus.KEPT_BLOCKED,
                resolved_at=datetime.now(UTC) if resolved_at is None else resolved_at,
            )
        with self._lock:
            item = self.get(intervention_id)
            updated = replace(item, status=InterventionStatus.KEPT_BLOCKED)
            self._items[intervention_id] = updated
            return updated

    def resolve_approved(
        self,
        intervention_id: str,
        approval_id: str,
        *,
        resolved_at: datetime | None = None,
    ) -> Intervention:
        if self._repository is not None:
            return self._repository.resolve_intervention(
                intervention_id,
                InterventionStatus.APPROVED,
                approval_id=approval_id,
                resolved_at=datetime.now(UTC) if resolved_at is None else resolved_at,
            )
        with self._lock:
            item = self.get(intervention_id)
            updated = replace(
                item,
                status=InterventionStatus.APPROVED,
                approval_id=approval_id,
            )
            self._items[intervention_id] = updated
            return updated
