from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sss_core.domain import Ecosystem, InstallRequest, PackageIdentity
from sss_core.policy.approvals import ApprovalScope

ROOT = Path(__file__).parents[2]


def _request() -> InstallRequest:
    return InstallRequest(
        request_id="request-1",
        project_id="project-1",
        agent_family="codex",
        package=PackageIdentity(Ecosystem.NPM, "https://registry.npmjs.org", "demo"),
        version_spec="1.0.0",
        direct_url=None,
        artifact_sha256="a" * 64,
        is_direct=True,
    )


def _scope(now: datetime) -> ApprovalScope:
    request = _request()
    return ApprovalScope(
        package=request.package,
        version="1.0.0",
        registry_origin=request.package.registry_origin,
        artifact_sha256="a" * 64,
        project_id=request.project_id,
        expires_at=now + timedelta(minutes=5),
        nonce="nonce-1",
        policy_version="sss-hackathon-v3",
    )


def test_exact_unexpired_scope_covers_request() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)

    assert _scope(now).covers(_request(), now=now)


@pytest.mark.parametrize(
    "change",
    [
        {"version_spec": "2.0.0"},
        {"project_id": "other-project"},
        {"artifact_sha256": "b" * 64},
        {
            "package": PackageIdentity(
                Ecosystem.NPM,
                "https://npm.example.invalid",
                "demo",
            )
        },
    ],
)
def test_altered_request_is_not_covered(change: dict[str, object]) -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)

    assert not _scope(now).covers(replace(_request(), **change), now=now)


def test_expired_scope_is_not_covered() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)

    assert not _scope(now).covers(_request(), now=now + timedelta(minutes=6))


def test_missing_or_invalid_artifact_hash_is_rejected() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)

    with pytest.raises(ValueError, match="artifact_sha256"):
        replace(_scope(now), artifact_sha256="")


def test_approved_json_claims_round_trip_through_scope() -> None:
    claims = json.loads(
        (ROOT / "docs/contracts/examples/approval-create-request.json").read_text(
            encoding="utf-8"
        )
    )

    scope = ApprovalScope.from_claims(claims)

    assert scope.to_claims() == claims


def test_claims_reject_unknown_fields_and_naive_expiry() -> None:
    now = datetime(2026, 9, 7, tzinfo=UTC)
    claims = _scope(now).to_claims()
    claims["unexpected"] = True
    with pytest.raises(ValueError, match="exactly"):
        ApprovalScope.from_claims(claims)

    with pytest.raises(ValueError, match="timezone"):
        replace(_scope(now), expires_at=datetime(2026, 9, 7))
