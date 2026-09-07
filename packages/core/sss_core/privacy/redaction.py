from __future__ import annotations

from collections.abc import Mapping

TELEMETRY_ALLOWLIST = (
    "schema_version",
    "idempotency_key",
    "ecosystem",
    "registry_origin",
    "canonical_name",
    "version_spec",
    "source_type",
    "agent_family",
    "policy_version",
    "occurred_at",
    "installation_attempt_id",
    "client_pseudonym",
)


def redact_client_event(event: Mapping[str, object]) -> dict[str, object]:
    return {key: event[key] for key in TELEMETRY_ALLOWLIST if key in event}
