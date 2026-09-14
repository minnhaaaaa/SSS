"""Validated production worker configuration."""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from os import environ
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class WorkerSettings:
    environment: str
    model_base_url: str
    model_id: str
    model_token_file: Path
    allow_private_http_model: bool
    request_timeout_seconds: float = 30.0
    max_response_bytes: int = 1_048_576
    concurrency: int = 2
    retry_attempts: int = 3
    prompt_manifest: Path | None = None

    @classmethod
    def from_env(cls, values: Mapping[str, str] | None = None) -> WorkerSettings:
        source = environ if values is None else values
        token_path = Path(source.get("SSS_MODEL_TOKEN_FILE", "")).expanduser()
        settings = cls(
            environment=source.get("SSS_ENV", "production").casefold(),
            model_base_url=source.get("SSS_MODEL_BASE_URL", "").rstrip("/"),
            model_id=source.get("SSS_MODEL_ID", ""),
            model_token_file=token_path,
            allow_private_http_model=source.get(
                "SSS_ALLOW_PRIVATE_HTTP_MODEL", "false"
            ).casefold()
            == "true",
            request_timeout_seconds=float(source.get("SSS_MODEL_TIMEOUT_SECONDS", "30")),
            max_response_bytes=int(source.get("SSS_MODEL_MAX_RESPONSE_BYTES", "1048576")),
            concurrency=int(source.get("SSS_WORKER_CONCURRENCY", "2")),
            retry_attempts=int(source.get("SSS_MODEL_RETRY_ATTEMPTS", "3")),
            prompt_manifest=(
                Path(value).expanduser()
                if (value := source.get("SSS_PROMPT_MANIFEST", "").strip())
                else None
            ),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        parsed = urlsplit(self.model_base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("SSS_MODEL_BASE_URL must be an absolute HTTP(S) URL")
        private_host = parsed.hostname == "localhost"
        with suppress(ValueError):
            private_host = private_host or ipaddress.ip_address(parsed.hostname).is_private
        if parsed.scheme != "https" and not (
            self.allow_private_http_model and private_host
        ):
            raise ValueError("production model URL requires HTTPS or explicit private HTTP")
        if not self.model_id:
            raise ValueError("SSS_MODEL_ID is required")
        if not self.model_token_file.is_file():
            raise ValueError("SSS_MODEL_TOKEN_FILE must exist")
        if self.model_token_file.stat().st_mode & 0o077:
            raise ValueError("model token file permissions must be 0600 or stricter")
        if not 0 < self.request_timeout_seconds <= 300:
            raise ValueError("model timeout must be between 0 and 300 seconds")
        if not 1 <= self.max_response_bytes <= 10_485_760:
            raise ValueError("model response limit is invalid")
        if not 1 <= self.concurrency <= 32 or not 1 <= self.retry_attempts <= 10:
            raise ValueError("worker concurrency or retry limit is invalid")

    def read_model_token(self) -> str:
        token = self.model_token_file.read_text(encoding="utf-8").strip()
        if not token:
            raise ValueError("model token file is empty")
        return token
