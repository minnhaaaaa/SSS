"""Safe on-disk CLI configuration with token indirection."""

from __future__ import annotations

import ipaddress
import json
import os
import tempfile
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from sss_cli.config import CliConfigurationError


def default_config_path(environment: Mapping[str, str] | None = None) -> Path:
    values = os.environ if environment is None else environment
    if root := values.get("XDG_CONFIG_HOME", "").strip():
        return Path(root).expanduser() / "sss" / "config.json"
    return Path.home() / ".config" / "sss" / "config.json"


def _server_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise CliConfigurationError("server must be an absolute URL without credentials")
    loopback = parsed.hostname == "localhost"
    with suppress(ValueError):
        loopback = loopback or ipaddress.ip_address(parsed.hostname).is_loopback
    if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
        raise CliConfigurationError("server must use HTTPS except on loopback")
    return value.strip().rstrip("/")


@dataclass(frozen=True, slots=True)
class StoredCliConfig:
    server: str
    token_file: Path
    organization_id: str
    project_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "server", _server_url(self.server))
        if not self.organization_id.strip() or not self.project_id.strip():
            raise CliConfigurationError("organization and project identifiers are required")
        token_file = self.token_file.expanduser().resolve()
        if not token_file.is_file():
            raise CliConfigurationError("token file does not exist")
        if token_file.stat().st_mode & 0o077:
            raise CliConfigurationError("token file permissions must be 0600 or stricter")
        object.__setattr__(self, "token_file", token_file)

    def read_token(self) -> str:
        token = self.token_file.read_text(encoding="utf-8").strip()
        if not token:
            raise CliConfigurationError("token file is empty")
        return token

    def to_json(self) -> dict[str, str]:
        return {
            "server": self.server,
            "token_file": str(self.token_file),
            "organization_id": self.organization_id,
            "project_id": self.project_id,
        }


def write_config(config: StoredCliConfig, path: Path) -> None:
    destination = path.expanduser().resolve()
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(destination.parent, 0o700)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".config-", suffix=".json", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(config.to_json(), handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def load_config(path: Path) -> StoredCliConfig:
    source = path.expanduser().resolve()
    if source.stat().st_mode & 0o077:
        raise CliConfigurationError("configuration file permissions must be 0600 or stricter")
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise TypeError
        return StoredCliConfig(
            server=str(document["server"]),
            token_file=Path(str(document["token_file"])),
            organization_id=str(document["organization_id"]),
            project_id=str(document["project_id"]),
        )
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise CliConfigurationError("configuration file is invalid") from exc
