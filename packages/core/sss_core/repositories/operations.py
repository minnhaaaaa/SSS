"""Durable operational-state contracts shared by API services and repositories."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from sss_core.auth import CredentialAuditRecord
from sss_core.domain import Decision, InstallRequest, PackageIdentity, PolicyDecision


class IdempotencyConflict(ValueError):
    """An idempotency key was reused for a different request."""


class ApprovalNonceConflict(ValueError):
    """An approval nonce does not exist, does not match, or was already consumed."""


class InterventionStatus(StrEnum):
    PENDING = "pending"
    KEPT_BLOCKED = "kept_blocked"
    APPROVED = "approved"


@dataclass(frozen=True, slots=True)
class InstallAttempt:
    decision_id: str
    manager: str
    arguments: tuple[str, ...]
    agent_family: str
    project_id: str
    decision: Decision
    child_started: bool
    attempted_at: datetime


@dataclass(frozen=True, slots=True)
class Intervention:
    intervention_id: str
    request: InstallRequest
    decision: PolicyDecision
    evidence_labels: tuple[str, ...]
    status: InterventionStatus
    created_at: datetime
    approval_id: str | None = None

    @property
    def package(self) -> PackageIdentity:
        return self.request.package


@dataclass(frozen=True, slots=True)
class IdempotencyClaim:
    idempotency_key: str
    request_hash: str
    response_reference: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OperationalEvent:
    event_id: int
    event_type: str
    payload: Mapping[str, Any]
    occurred_at: datetime


class OperationalRepository(Protocol):
    def record_credential_audit(self, record: CredentialAuditRecord) -> None: ...

    def record_decision(
        self,
        request: InstallRequest,
        decision: PolicyDecision,
        *,
        evidence_as_of: datetime,
        evidence_attestation: str,
    ) -> None: ...

    def record_attempt(
        self, attempt: InstallAttempt, *, attempt_id: str | None = None
    ) -> InstallAttempt: ...

    def get_attempt(self, attempt_id: str) -> InstallAttempt | None: ...

    def list_attempts(self, *, limit: int = 100) -> tuple[InstallAttempt, ...]: ...

    def create_intervention(self, intervention: Intervention) -> Intervention: ...

    def list_interventions(
        self, *, pending_only: bool = False, limit: int = 100
    ) -> tuple[Intervention, ...]: ...

    def get_intervention(self, intervention_id: str) -> Intervention: ...

    def resolve_intervention(
        self,
        intervention_id: str,
        status: InterventionStatus,
        *,
        approval_id: str | None = None,
        resolved_at: datetime,
    ) -> Intervention: ...

    def claim_idempotency(
        self, idempotency_key: str, request_hash: str, response_reference: str
    ) -> IdempotencyClaim: ...

    def get_idempotency(self, idempotency_key: str) -> IdempotencyClaim | None: ...

    def consume_approval_nonce(
        self,
        approval_id: str,
        nonce: str,
        request_id: str,
        *,
        consumed_at: datetime,
        metadata: Mapping[str, Any],
    ) -> None: ...

    def append_event(
        self,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        occurred_at: datetime,
    ) -> OperationalEvent: ...

    def events_after(
        self, *, after_id: int = 0, limit: int = 100
    ) -> tuple[OperationalEvent, ...]: ...
