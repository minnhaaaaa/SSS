"""Strict idempotency-key validation for write routes."""

from __future__ import annotations

import re

from fastapi import Header, HTTPException, Request, status

_SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


def validate_idempotency_key(value: str, *, max_bytes: int) -> str:
    encoded = value.encode("utf-8")
    if not encoded or len(encoded) > max_bytes or not _SAFE_KEY.fullmatch(value):
        raise ValueError("invalid idempotency key")
    return value


async def require_idempotency_key(
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str:
    if idempotency_key is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )
    try:
        return validate_idempotency_key(
            idempotency_key,
            max_bytes=request.app.state.settings.idempotency_key_max_bytes,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is invalid",
        ) from exc
