"""Authentication dependencies shared by protected API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, Request, status
from sss_core.auth import (
    CredentialAuditRecord,
    CredentialAuthenticationError,
    CredentialAuthorizationError,
)


def _audit(
    request: Request,
    *,
    credential_id: str | None,
    scope: str,
    outcome: str,
) -> None:
    sink = getattr(request.app.state, "credential_audit_sink", None)
    if sink is None:
        return
    sink(
        CredentialAuditRecord(
            audit_id=uuid4().hex,
            credential_id=credential_id or "unmatched",
            route=request.url.path,
            required_scope=scope,
            outcome=outcome,
            request_id=getattr(request.state, "request_id", None),
            occurred_at=datetime.now(UTC),
        )
    )


def require_scope(scope: str):  # type: ignore[no-untyped-def]
    async def dependency(request: Request):  # type: ignore[no-untyped-def]
        if not request.app.state.credentials.configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="API authentication is not configured",
            )
        scheme, separator, credential = request.headers.get("Authorization", "").partition(" ")
        if not separator or scheme.casefold() != "bearer" or not credential:
            _audit(request, credential_id=None, scope=scope, outcome="missing")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            principal = request.app.state.credentials.authenticate(credential, scope)
        except CredentialAuthenticationError as exc:
            _audit(
                request,
                credential_id=exc.credential_id,
                scope=scope,
                outcome="unauthenticated",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        except CredentialAuthorizationError as exc:
            _audit(
                request,
                credential_id=exc.credential_id,
                scope=scope,
                outcome="forbidden",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Credential lacks required scope",
            ) from exc
        request.state.credential = principal
        _audit(
            request,
            credential_id=principal.credential_id,
            scope=scope,
            outcome="allowed",
        )
        return principal

    return dependency


require_service_token = require_scope("agent:check")
