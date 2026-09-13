"""HMAC-signed, exact-scope, single-use approval grants."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from threading import RLock

from sss_core import InstallRequest
from sss_core.policy.approvals import ApprovalScope


class ApprovalError(ValueError):
    """Raised when a grant is invalid, expired, widened or replayed."""


@dataclass(frozen=True, slots=True)
class ApprovalGrant:
    approval_id: str
    token: str
    scope: ApprovalScope
    request_id: str
    intervention_id: str
    consumed: bool = False


class ApprovalService:
    def __init__(self, *, signing_key: bytes) -> None:
        if len(signing_key) < 32:
            raise ValueError("approval signing key must contain at least 32 bytes")
        self._signing_key = signing_key
        self._by_token: dict[str, ApprovalGrant] = {}
        self._by_intervention: dict[str, ApprovalGrant] = {}
        self._lock = RLock()

    def issue(
        self,
        *,
        intervention_id: str,
        request: InstallRequest,
        scope: ApprovalScope,
        now: datetime | None = None,
    ) -> ApprovalGrant:
        issued_at = datetime.now(UTC) if now is None else now
        if not scope.covers(request, now=issued_at):
            raise ApprovalError("approval claims do not exactly cover the blocked request")
        payload = _canonical_json(scope.to_claims())
        signature = hmac.new(self._signing_key, payload, hashlib.sha256).digest()
        token = f"{_encode(payload)}.{_encode(signature)}"
        approval_id = hashlib.sha256(token.encode()).hexdigest()
        grant = ApprovalGrant(
            approval_id=approval_id,
            token=token,
            scope=scope,
            request_id=request.request_id,
            intervention_id=intervention_id,
        )
        with self._lock:
            existing = self._by_intervention.get(intervention_id)
            if existing is not None:
                if existing.scope != scope:
                    raise ApprovalError("intervention already has a different approval")
                return existing
            self._by_token[token] = grant
            self._by_intervention[intervention_id] = grant
        return grant

    def consume(
        self,
        *,
        token: str,
        request_id: str,
        expected_nonce: str,
        request: InstallRequest | None = None,
        now: datetime | None = None,
    ) -> ApprovalGrant:
        current_time = datetime.now(UTC) if now is None else now
        try:
            encoded_payload, encoded_signature = token.split(".", maxsplit=1)
            payload = _decode(encoded_payload)
            provided_signature = _decode(encoded_signature)
            expected_signature = hmac.new(self._signing_key, payload, hashlib.sha256).digest()
            if not hmac.compare_digest(provided_signature, expected_signature):
                raise ApprovalError("approval signature is invalid")
            claims = json.loads(payload)
            if not isinstance(claims, dict):
                raise ApprovalError("approval claims are invalid")
            scope = ApprovalScope.from_claims(claims)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            if isinstance(exc, ApprovalError):
                raise
            raise ApprovalError("approval token is invalid") from exc
        if scope.nonce != expected_nonce:
            raise ApprovalError("approval nonce does not match")
        if current_time >= scope.expires_at:
            raise ApprovalError("approval has expired")
        if request is not None and not scope.covers(request, now=current_time):
            raise ApprovalError("approval does not exactly cover this install request")
        with self._lock:
            grant = self._by_token.get(token)
            if grant is None or grant.scope != scope:
                raise ApprovalError("approval was not issued by this service")
            if grant.request_id != request_id:
                raise ApprovalError("approval request does not match")
            if grant.consumed:
                raise ApprovalError("approval has already been consumed")
            consumed = replace(grant, consumed=True)
            self._by_token[token] = consumed
            self._by_intervention[grant.intervention_id] = consumed
            return consumed


def _canonical_json(claims: dict[str, object]) -> bytes:
    return json.dumps(claims, separators=(",", ":"), sort_keys=True).encode()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(value + padding, altchars=b"-_", validate=True)
