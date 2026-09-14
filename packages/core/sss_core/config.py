from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

_SCHEMA = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


@dataclass(frozen=True)
class ExasolSettings:
    dsn: str
    user: str
    password: str = field(repr=False)
    schema: str

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> ExasolSettings:
        password = _secret_value(
            values,
            value_key="SSS_EXASOL_PASSWORD",
            file_key="SSS_EXASOL_PASSWORD_FILE",
        )
        required = (
            "SSS_EXASOL_DSN",
            "SSS_EXASOL_USER",
            "SSS_EXASOL_SCHEMA",
        )
        missing = [name for name in required if not values.get(name, "").strip()]
        if not password:
            missing.append("SSS_EXASOL_PASSWORD or SSS_EXASOL_PASSWORD_FILE")
        if missing:
            raise ValueError(f"missing required Exasol setting(s): {', '.join(missing)}")
        dsn = values["SSS_EXASOL_DSN"].strip()
        user = values["SSS_EXASOL_USER"].strip()
        schema = values["SSS_EXASOL_SCHEMA"].strip().upper()
        if any(character.isspace() for character in dsn):
            raise ValueError("SSS_EXASOL_DSN must not contain whitespace")
        if not _SCHEMA.fullmatch(schema):
            raise ValueError("Exasol schema must be an unquoted uppercase identifier")
        return cls(dsn=dsn, user=user, password=password, schema=schema)

    @classmethod
    def from_env(cls) -> ExasolSettings:
        return cls.from_mapping(os.environ)


def _secret_value(
    values: Mapping[str, str], *, value_key: str, file_key: str
) -> str:
    inline = values.get(value_key, "")
    filename = values.get(file_key, "").strip()
    if inline and filename:
        raise ValueError(f"configure only one of {value_key} and {file_key}")
    if not filename:
        return inline
    try:
        return Path(filename).read_text(encoding="utf-8").rstrip("\r\n")
    except OSError as exc:
        raise ValueError(f"{file_key} is unreadable") from exc
