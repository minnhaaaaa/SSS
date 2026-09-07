from __future__ import annotations

from sss_core.privacy.redaction import redact_client_event


def test_only_allowlisted_telemetry_leaves_the_process() -> None:
    event = {
        "schema_version": "1",
        "idempotency_key": "attempt-1",
        "ecosystem": "npm",
        "registry_origin": "https://registry.npmjs.org",
        "canonical_name": "synthetic-demo",
        "version_spec": "1.0.0",
        "source_type": "registry",
        "agent_family": "codex",
        "policy_version": "sss-hackathon-v3",
        "occurred_at": "2026-09-07T12:00:00Z",
        "installation_attempt_id": "attempt-1",
        "client_pseudonym": "rotating-client-1",
        "prompt": "secret prompt",
        "code": "print('secret')",
        "environment": {"TOKEN": "secret"},
        "username": "alice",
        "path": "/home/alice/private",
        "repository_name": "private-repo",
    }

    redacted = redact_client_event(event)

    assert redacted == {
        key: event[key]
        for key in (
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
    }
