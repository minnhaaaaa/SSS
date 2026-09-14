from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sss_api.services.approvals import ApprovalError, ApprovalService
from sss_core import Ecosystem, InstallRequest, PackageIdentity
from sss_core.policy.approvals import ApprovalScope
from sss_core.repositories.operations import ApprovalNonceConflict, ApprovalRecord


class DurableApprovalRepository:
    def __init__(self) -> None:
        self.records: dict[str, ApprovalRecord] = {}

    def create_approval(self, record: ApprovalRecord) -> ApprovalRecord:
        existing = self.records.setdefault(record.approval_id, record)
        if existing != record:
            raise ValueError("approval id collision")
        return existing

    def get_approval(self, approval_id: str) -> ApprovalRecord | None:
        return self.records.get(approval_id)

    def consume_approval_nonce(
        self,
        approval_id: str,
        nonce: str,
        request_id: str,
        *,
        consumed_at: datetime,
        metadata: dict[str, object],
    ) -> None:
        del metadata
        record = self.records.get(approval_id)
        if (
            record is None
            or record.nonce != nonce
            or record.request_id != request_id
            or record.expires_at <= consumed_at
            or record.consumed_at is not None
        ):
            raise ApprovalNonceConflict("approval nonce is invalid or already consumed")
        self.records[approval_id] = record.with_consumed_at(consumed_at)


def _request() -> InstallRequest:
    return InstallRequest(
        request_id="request-restart",
        project_id="project-1",
        agent_family="codex",
        package=PackageIdentity(Ecosystem.NPM, "https://registry.npmjs.org", "safe-lib"),
        version_spec="1.0.0",
        direct_url=None,
        artifact_sha256="a" * 64,
        is_direct=True,
    )


def test_approval_survives_service_restart_and_replay_does_not() -> None:
    now = datetime(2026, 9, 14, tzinfo=UTC)
    request = _request()
    scope = ApprovalScope(
        package=request.package,
        version="1.0.0",
        registry_origin=request.package.registry_origin,
        artifact_sha256="a" * 64,
        project_id=request.project_id,
        expires_at=now + timedelta(minutes=5),
        nonce="restart-nonce",
        policy_version="sss-hackathon-v3",
    )
    repository = DurableApprovalRepository()
    key = b"production-signing-key-with-32-bytes-minimum"

    issued = ApprovalService(signing_key=key, repository=repository).issue(
        intervention_id="intervention-1", request=request, scope=scope, now=now
    )
    consumed = ApprovalService(signing_key=key, repository=repository).consume(
        token=issued.token,
        request_id=request.request_id,
        expected_nonce=scope.nonce,
        now=now + timedelta(seconds=1),
    )

    assert consumed.consumed is True
    with pytest.raises(ApprovalError, match="already been consumed"):
        ApprovalService(signing_key=key, repository=repository).consume(
            token=issued.token,
            request_id=request.request_id,
            expected_nonce=scope.nonce,
            now=now + timedelta(seconds=2),
        )
