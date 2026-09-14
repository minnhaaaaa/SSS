#!/usr/bin/env python3
"""Verify and restore a logical SSS backup into a migrated empty schema."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Protocol, cast

from sss_core.config import ExasolSettings

_IDENTIFIER = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


class RestoreError(ValueError):
    pass


class RestoreConnection(Protocol):
    def execute(
        self, sql: str, query_params: dict[str, object] | None = None
    ) -> Any: ...

    def import_from_file(self, source: str, table: str) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


def _rows(result: Any) -> list[tuple[Any, ...]]:
    return list(result.fetchall())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _count_table(connection: RestoreConnection, table: str) -> int:
    if not _IDENTIFIER.fullmatch(table):
        raise RestoreError("unsafe table identifier")
    # Manifest table identifiers cannot be bound and have already passed the strict allowlist.
    return int(_rows(connection.execute(f"SELECT COUNT(*) FROM {table}"))[0][0])  # noqa: S608


def restore_backup(
    connection: RestoreConnection,
    *,
    schema: str,
    source: Path,
    allow_nonempty: bool = False,
) -> dict[str, object]:
    schema_name = schema.strip().upper()
    if not _IDENTIFIER.fullmatch(schema_name):
        raise RestoreError("schema must be an uppercase unquoted identifier")
    try:
        manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RestoreError("backup manifest is missing or invalid") from exc
    if not isinstance(manifest, dict) or manifest.get("format_version") != 1:
        raise RestoreError("backup format is unsupported")
    raw_files = manifest.get("files")
    raw_counts = manifest.get("table_counts")
    if not isinstance(raw_files, list) or not isinstance(raw_counts, dict):
        raise RestoreError("backup manifest is incomplete")
    files = cast(list[dict[str, object]], raw_files)
    counts = cast(dict[str, object], raw_counts)
    for item in files:
        table = str(item.get("table", ""))
        relative = str(item.get("path", ""))
        if not _IDENTIFIER.fullmatch(table) or relative != f"{table}.csv":
            raise RestoreError("backup contains an unsafe table path")
        path = source / relative
        if not path.is_file() or _sha256(path) != item.get("sha256"):
            raise RestoreError(f"backup file hash mismatch: {relative}")
    migration_rows = _rows(
        connection.execute("SELECT VERSION, CHECKSUM FROM SCHEMA_MIGRATIONS ORDER BY VERSION")
    )
    expected_migrations = manifest.get("migrations")
    actual_migrations = [
        {"version": str(row[0]), "checksum": str(row[1])} for row in migration_rows
    ]
    if actual_migrations != expected_migrations:
        raise RestoreError("target migration versions do not match the backup")
    data_tables = {table: count for table, count in counts.items() if table != "SCHEMA_MIGRATIONS"}
    existing = {
        table: _count_table(connection, table)
        for table in data_tables
        if _IDENTIFIER.fullmatch(table)
    }
    if any(existing.values()) and not allow_nonempty:
        raise RestoreError("target schema is nonempty; pass --allow-nonempty to override")
    try:
        for item in files:
            table = str(item["table"])
            if table == "SCHEMA_MIGRATIONS":
                continue
            connection.import_from_file(str(source / str(item["path"])), table)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    restored = {table: _count_table(connection, table) for table in counts}
    if any(not isinstance(value, int) or isinstance(value, bool) for value in counts.values()):
        raise RestoreError("backup table counts are invalid")
    expected = {table: value for table, value in counts.items() if isinstance(value, int)}
    if restored != expected:
        raise RestoreError("restored table counts do not match the manifest")
    return {**manifest, "schema": schema_name, "table_counts": restored}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--allow-nonempty", action="store_true")
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
        manifest = restore_backup(
            connection,
            schema=settings.schema,
            source=args.source.resolve(),
            allow_nonempty=args.allow_nonempty,
        )
        print(json.dumps(manifest, sort_keys=True))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
