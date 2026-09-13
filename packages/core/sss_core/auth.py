"""Digest-backed, scope-limited service credentials."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from hmac import compare_digest
from pathlib import Path
from typing import Any

KNOWN_SCOPES = frozenset(
    {
        "agent:check",
        "collector:write",
        "radar:read",
        "approval:write",
        "operator:intervene",
    }
)
_IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class CredentialAuthenticationError(ValueError):
    """The bearer token did not identify an enabled credential."""

    def __init__(self, message: str, credential_id: str | None = None) -> None:
        super().__init__(message)
        self.credential_id = credential_id


class CredentialAuthorizationError(PermissionError):
    """The credential does not own the required scope."""

    def __init__(self, message: str, credential_id: str) -> None:
        super().__init__(message)
        self.credential_id = credential_id


@dataclass(frozen=True, slots=True)
class CredentialAuditRecord:
    audit_id: str
    credential_id: str
    route: str
    required_scope: str
    outcome: str
    request_id: str | None
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class CredentialPrincipal:
    credential_id: str
    scopes: frozenset[str]


@dataclass(frozen=True, slots=True)
class CredentialRecord:
    credential_id: str
    token_sha256: str
    scopes: frozenset[str]
    enabled: bool = True

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.credential_id):
            raise ValueError("credential_id must be a stable identifier")
        if not _DIGEST.fullmatch(self.token_sha256):
            raise ValueError("token_sha256 must be a lowercase SHA-256 digest")
        unknown = self.scopes - KNOWN_SCOPES
        if unknown or not self.scopes:
            raise ValueError(f"credential contains unknown or empty scope set: {sorted(unknown)}")

    def to_json(self) -> dict[str, Any]:
        return {
            "credential_id": self.credential_id,
            "token_sha256": self.token_sha256,
            "scopes": sorted(self.scopes),
            "enabled": self.enabled,
        }

    @classmethod
    def from_json(cls, value: object) -> CredentialRecord:
        if not isinstance(value, dict):
            raise ValueError("credential must be an object")
        expected = {"credential_id", "token_sha256", "scopes", "enabled"}
        unknown = set(value) - expected
        if unknown:
            raise ValueError(f"credential contains unknown fields: {sorted(unknown)}")
        if set(value) != expected:
            raise ValueError("credential is missing required fields")
        scopes = value["scopes"]
        if not isinstance(scopes, list) or not all(isinstance(item, str) for item in scopes):
            raise ValueError("credential scopes must be a string array")
        if not isinstance(value["enabled"], bool):
            raise ValueError("credential enabled must be boolean")
        return cls(
            credential_id=str(value["credential_id"]),
            token_sha256=str(value["token_sha256"]),
            scopes=frozenset(scopes),
            enabled=value["enabled"],
        )


class CredentialStore:
    def __init__(self, records: tuple[CredentialRecord, ...]) -> None:
        identifiers = [record.credential_id for record in records]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("duplicate credential_id")
        self._records = records

    @property
    def configured(self) -> bool:
        return bool(self._records)

    @classmethod
    def from_file(cls, path: Path) -> CredentialStore:
        if path.stat().st_mode & 0o077:
            raise ValueError("credentials file permissions must not allow group or other access")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("credentials file is unreadable or invalid JSON") from exc
        if not isinstance(document, dict) or set(document) != {"credentials"}:
            raise ValueError("credentials file must contain only a credentials array")
        values = document["credentials"]
        if not isinstance(values, list) or not values:
            raise ValueError("credentials must be a non-empty array")
        return cls(tuple(CredentialRecord.from_json(value) for value in values))

    @classmethod
    def from_raw_tokens(cls, raw_tokens: tuple[str, ...]) -> CredentialStore:
        return cls(
            tuple(
                CredentialRecord(
                    credential_id=f"legacy-{index}",
                    token_sha256=sha256(token.encode()).hexdigest(),
                    scopes=KNOWN_SCOPES,
                )
                for index, token in enumerate(raw_tokens, start=1)
            )
        )

    def authenticate(self, raw_token: str, required_scope: str) -> CredentialPrincipal:
        if required_scope not in KNOWN_SCOPES:
            raise ValueError(f"unknown required scope: {required_scope}")
        supplied_digest = sha256(raw_token.encode()).hexdigest()
        matched: CredentialRecord | None = None
        for record in self._records:
            if compare_digest(supplied_digest, record.token_sha256):
                matched = record
        if matched is None or not matched.enabled:
            raise CredentialAuthenticationError(
                "invalid or disabled credential",
                None if matched is None else matched.credential_id,
            )
        if required_scope not in matched.scopes:
            raise CredentialAuthorizationError(
                "credential lacks required scope", matched.credential_id
            )
        return CredentialPrincipal(matched.credential_id, matched.scopes)
