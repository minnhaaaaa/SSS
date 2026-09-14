from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.backup_exasol import create_backup
from scripts.restore_exasol import RestoreError, restore_backup


class Rows:
    def __init__(self, values: list[tuple[Any, ...]]) -> None:
        self.values = values

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.values


class MemoryExportConnection:
    def __init__(self, tables: dict[str, list[list[object]]]) -> None:
        self.tables = tables

    def execute(self, sql: str, params: dict[str, object] | None = None) -> Rows:
        normalized = " ".join(sql.upper().split())
        if "FROM EXA_ALL_TABLES" in normalized:
            return Rows([(name,) for name in sorted(self.tables)])
        if normalized.startswith("SELECT COUNT(*) FROM"):
            return Rows([(len(self.tables[normalized.rsplit(" ", 1)[-1]]),)])
        if "FROM SCHEMA_MIGRATIONS" in normalized:
            return Rows(
                [tuple(row) for row in self.tables.get("SCHEMA_MIGRATIONS", [])]
            )
        raise AssertionError((sql, params))

    def export_to_file(self, destination: str, table: str) -> None:
        Path(destination).write_text(
            "\n".join(json.dumps(row) for row in self.tables[table]) + "\n",
            encoding="utf-8",
        )

    def import_from_file(self, source: str, table: str) -> None:
        self.tables[table] = [
            json.loads(line)
            for line in Path(source).read_text(encoding="utf-8").splitlines()
            if line
        ]

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


def test_backup_restore_preserves_counts_attestation_and_manifest(tmp_path: Path) -> None:
    source = MemoryExportConnection(
        {
            "POLICY_DECISIONS": [["decision-1", "e" * 64]],
            "EVENT_LOG": [[1, "install.blocked"]],
            "APPROVAL_GRANTS": [["approval-1", "consumed"]],
            "SCHEMA_MIGRATIONS": [["001_initial_evidence", "a" * 64]],
        }
    )
    backup = tmp_path / "backup"
    manifest = create_backup(source, schema="SSS", destination=backup)
    target = MemoryExportConnection({name: [] for name in source.tables})
    target.tables["SCHEMA_MIGRATIONS"] = source.tables["SCHEMA_MIGRATIONS"].copy()

    restored = restore_backup(target, schema="SSS", source=backup)

    assert restored["table_counts"] == manifest["table_counts"]
    assert target.tables == source.tables
    assert len(manifest["files"]) == 4
    assert all(len(item["sha256"]) == 64 for item in manifest["files"])


def test_restore_refuses_hash_mismatch_and_nonempty_target(tmp_path: Path) -> None:
    source = MemoryExportConnection({"POLICY_DECISIONS": [["decision-1", "e" * 64]]})
    backup = tmp_path / "backup"
    create_backup(source, schema="SSS", destination=backup)
    target = MemoryExportConnection({"POLICY_DECISIONS": [["existing"]]})

    with pytest.raises(RestoreError, match="nonempty"):
        restore_backup(target, schema="SSS", source=backup)

    target.tables["POLICY_DECISIONS"] = []
    (backup / "POLICY_DECISIONS.csv").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(RestoreError, match="hash"):
        restore_backup(target, schema="SSS", source=backup)
