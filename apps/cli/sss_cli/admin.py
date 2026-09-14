"""Administrative credential generation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from secrets import token_urlsafe

from sss_core.auth import CredentialRecord


@dataclass(frozen=True, slots=True)
class GeneratedCredential:
    raw_token: str
    record: CredentialRecord


def generate_token(
    credential_id: str, scopes: frozenset[str]
) -> GeneratedCredential:
    raw_token = token_urlsafe(32)
    return GeneratedCredential(
        raw_token=raw_token,
        record=CredentialRecord(
            credential_id=credential_id,
            token_sha256=sha256(raw_token.encode()).hexdigest(),
            scopes=scopes,
            enabled=True,
        ),
    )
