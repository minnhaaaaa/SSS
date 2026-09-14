#!/usr/bin/env python3
"""Create a checksummed logical backup of one migrated SSS schema."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Protocol

from sss_core.config import ExasolSettings

_IDENTIFIER = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


class BackupConnection(Protocol):
    def execute(
        self, sql: str, query_params: dict[str, object] | None = None
    ) -> Any: ...

    def export_to_file(self, destination: str, table: str) -> None: ...


def _rows(result: Any) -> list[tuple[Any, ...]]:
    return list(result.fetchall())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _application_version() -> str:
    try:
        return version("stop-slop-squatting")
    except PackageNotFoundError:
        return "0.2.0"


def _count_table(connection: BackupConnection, table: str) -> int:
    if not _IDENTIFIER.fullmatch(table):
        raise ValueError("unsafe table identifier")
    # Table identifiers cannot be bound; the name came from EXA_ALL_TABLES and is revalidated.
    return int(_rows(connection.execute(f"SELECT COUNT(*) FROM {table}"))[0][0])  # noqa: S608


def create_backup(
    connection: BackupConnection, *, schema: str, destination: Path
) -> dict[str, object]:
    schema_name = schema.strip().upper()
    if not _IDENTIFIER.fullmatch(schema_name):
        raise ValueError("schema must be an uppercase unquoted identifier")
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError("backup destination must be empty")
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    tables = [
        str(row[0])
        for row in _rows(
            connection.execute(
                "SELECT TABLE_NAME FROM EXA_ALL_TABLES WHERE TABLE_SCHEMA={schema} "
                "ORDER BY TABLE_NAME",
                {"schema": schema_name},
            )
        )
    ]
    if not tables or any(not _IDENTIFIER.fullmatch(table) for table in tables):
        raise ValueError("source schema has no valid tables")
    counts: dict[str, int] = {}
    files: list[dict[str, object]] = []
    for table in tables:
        counts[table] = _count_table(connection, table)
        filename = f"{table}.csv"
        output = destination / filename
        connection.export_to_file(str(output), table)
        files.append(
            {
                "table": table,
                "path": filename,
                "bytes": output.stat().st_size,
                "sha256": _sha256(output),
            }
        )
    migrations = (
        [
            {"version": str(row[0]), "checksum": str(row[1])}
            for row in _rows(
                connection.execute(
                    "SELECT VERSION, CHECKSUM FROM SCHEMA_MIGRATIONS ORDER BY VERSION"
                )
            )
        ]
        if "SCHEMA_MIGRATIONS" in tables
        else []
    )
    manifest: dict[str, object] = {
        "format_version": 1,
        "application_version": _application_version(),
        "schema": schema_name,
        "created_at": datetime.now(UTC).isoformat(),
        "migrations": migrations,
        "table_counts": counts,
        "files": files,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    settings = ExasolSettings.from_env()
    import pyexasol  # type: ignore[import-untyped]

    connection = pyexasol.connect(
        dsn=settings.dsn,
        user=settings.user,
        password=settings.password,
        schema=settings.schema,
        autocommit=False,
    )
    try:
        manifest = create_backup(
            connection, schema=settings.schema, destination=args.destination.resolve()
        )
        print(json.dumps(manifest, sort_keys=True))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
