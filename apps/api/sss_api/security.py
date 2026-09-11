"""Authentication dependencies shared by protected API routes."""

from __future__ import annotations

from secrets import compare_digest

from fastapi import HTTPException, Request, status


def require_service_token(request: Request) -> None:
    settings = request.app.state.settings
    configured: tuple[str, ...] = settings.bearer_tokens
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured",
        )

    scheme, separator, credential = request.headers.get("Authorization", "").partition(" ")
    authenticated = (
        bool(separator)
        and scheme.casefold() == "bearer"
        and any(compare_digest(credential, expected) for expected in configured)
    )
    if not authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
