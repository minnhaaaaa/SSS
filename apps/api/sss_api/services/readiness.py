"""Runtime readiness checks for policy and optional Exasol persistence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from sss_core.policy.engine import POLICY_VERSION
from sss_core.repositories.exasol import ExasolConnection, SchemaReadiness

from sss_api.config import ApiSettings


class SchemaChecker(Protocol):
    def check(self, connection: ExasolConnection) -> SchemaReadiness: ...


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    ready: bool
    policy: dict[str, object]
    exasol: dict[str, object]


class ReadinessService:
    """Evaluate dependencies on demand so readiness cannot become stale."""

    def __init__(
        self,
        *,
        settings: ApiSettings,
        connection: ExasolConnection | None,
        schema_checker: SchemaChecker,
    ) -> None:
        self._settings = settings
        self._connection = connection
        self._schema_checker = schema_checker

    def check(self) -> ReadinessReport:
        policy_ready = self._settings.policy_version == POLICY_VERSION
        policy = {
            "ready": policy_ready,
            "configured_version": self._settings.policy_version,
            "engine_version": POLICY_VERSION,
        }
        if not self._settings.exasol_required:
            return ReadinessReport(
                ready=policy_ready,
                policy=policy,
                exasol={"ready": True, "required": False, "status": "not_required"},
            )
        if self._connection is None:
            return ReadinessReport(
                ready=False,
                policy=policy,
                exasol={"ready": False, "required": True, "status": "unavailable"},
            )
        try:
            schema = self._schema_checker.check(self._connection)
        except Exception as exc:  # the health boundary must report, not crash
            return ReadinessReport(
                ready=False,
                policy=policy,
                exasol={
                    "ready": False,
                    "required": True,
                    "status": "unavailable",
                    "error": type(exc).__name__,
                },
            )
        return ReadinessReport(
            ready=policy_ready and schema.ready,
            policy=policy,
            exasol={
                "ready": schema.ready,
                "required": True,
                "status": "ready" if schema.ready else "schema_unready",
                **asdict(schema),
            },
        )
