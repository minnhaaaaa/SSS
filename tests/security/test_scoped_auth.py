from __future__ import annotations

import json
from hashlib import sha256

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sss_api.security import require_scope
from sss_core.auth import CredentialRecord, CredentialStore


def _record(identifier: str, raw: str, *scopes: str, enabled: bool = True) -> CredentialRecord:
    return CredentialRecord(
        identifier, sha256(raw.encode()).hexdigest(), frozenset(scopes), enabled
    )


def test_missing_wrong_scope_disabled_and_valid_credentials() -> None:
    app = FastAPI()
    audits = []
    app.state.credential_audit_sink = audits.append
    app.state.credentials = CredentialStore(
        (
            _record("agent", "agent-raw-token", "agent:check"),
            _record("radar", "radar-raw-token", "radar:read"),
            _record("disabled", "disabled-token", "radar:read", enabled=False),
        )
    )

    @app.get("/v1/radar", dependencies=[Depends(require_scope("radar:read"))])
    async def radar() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/v1/radar").status_code == 401
    assert client.get(
        "/v1/radar", headers={"Authorization": "Bearer agent-raw-token"}
    ).status_code == 403
    assert client.get(
        "/v1/radar", headers={"Authorization": "Bearer disabled-token"}
    ).status_code == 401
    assert client.get(
        "/v1/radar", headers={"Authorization": "Bearer radar-raw-token"}
    ).status_code == 200
    assert [audit.outcome for audit in audits] == [
        "missing",
        "forbidden",
        "unauthenticated",
        "allowed",
    ]
    assert "raw-token" not in repr(audits)


def test_credentials_file_rejects_plaintext_duplicate_and_insecure_mode(tmp_path) -> None:
    path = tmp_path / "credentials.json"
    path.write_text(
        json.dumps(
            {
                "credentials": [
                    {
                        "credential_id": "agent",
                        "token": "raw-secret",
                        "token_sha256": "a" * 64,
                        "scopes": ["agent:check"],
                        "enabled": True,
                    }
                ]
            }
        )
    )
    path.chmod(0o600)
    with pytest.raises(ValueError, match="unknown fields"):
        CredentialStore.from_file(path)

    path.write_text(
        json.dumps(
            {
                "credentials": [
                    {
                        "credential_id": "agent",
                        "token_sha256": "a" * 64,
                        "scopes": ["agent:check"],
                        "enabled": True,
                    },
                    {
                        "credential_id": "agent",
                        "token_sha256": "b" * 64,
                        "scopes": ["agent:check"],
                        "enabled": True,
                    },
                ]
            }
        )
    )
    with pytest.raises(ValueError, match="duplicate"):
        CredentialStore.from_file(path)
    path.chmod(0o644)
    with pytest.raises(ValueError, match="permissions"):
        CredentialStore.from_file(path)


def test_record_validation_rejects_unknown_scope_and_malformed_digest() -> None:
    with pytest.raises(ValueError, match="scope"):
        CredentialRecord("bad", "a" * 64, frozenset({"root"}), True)
    with pytest.raises(ValueError, match="digest"):
        CredentialRecord("bad", "ABC", frozenset({"agent:check"}), True)
