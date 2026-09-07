from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from sss_core.domain import CandidateStatus, PackageIdentity, RegistryStatus


class ExasolResult(Protocol):
    def fetchall(self) -> Sequence[Sequence[Any]]: ...


class ExasolConnection(Protocol):
    def execute(
        self,
        sql: str,
        query_params: Mapping[str, Any] | None = None,
    ) -> ExasolResult | Sequence[Sequence[Any]]: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


def _rows(result: ExasolResult | Sequence[Sequence[Any]]) -> Sequence[Sequence[Any]]:
    if hasattr(result, "fetchall"):
        return result.fetchall()
    return result


def _statements(document: str) -> tuple[str, ...]:
    lines = [line for line in document.splitlines() if not line.lstrip().startswith("--")]
    statements = "\n".join(lines).split(";")
    return tuple(statement.strip() for statement in statements if statement.strip())


class MigrationRunner:
    def __init__(self, migrations_directory: Path) -> None:
        self._directory = migrations_directory

    def migrate(self, connection: ExasolConnection) -> tuple[str, ...]:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS SCHEMA_MIGRATIONS ("
            "VERSION VARCHAR(200) PRIMARY KEY, CHECKSUM VARCHAR(64) NOT NULL, "
            "APPLIED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        applied: list[str] = []
        try:
            for path in sorted(self._directory.glob("[0-9][0-9][0-9]_*.sql")):
                version = path.stem
                existing = connection.execute(
                    "SELECT VERSION FROM SCHEMA_MIGRATIONS WHERE VERSION = {version}",
                    {"version": version},
                )
                if _rows(existing):
                    continue
                document = path.read_text(encoding="utf-8")
                for statement in _statements(document):
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO SCHEMA_MIGRATIONS (VERSION, CHECKSUM, APPLIED_AT) "
                    "VALUES ({version}, {checksum}, CURRENT_TIMESTAMP)",
                    {
                        "version": version,
                        "checksum": hashlib.sha256(document.encode()).hexdigest(),
                    },
                )
                applied.append(version)
            if applied:
                views_directory = self._directory.parent / "views"
                for path in sorted(views_directory.glob("*.sql")):
                    for statement in _statements(path.read_text(encoding="utf-8")):
                        connection.execute(statement)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return tuple(applied)


@dataclass(frozen=True)
class RegistryEvidenceRecord:
    check_id: str
    package: PackageIdentity
    endpoint: str
    status: RegistryStatus
    http_status: int | None
    checked_at: datetime
    response_sha256: str | None
    error_class: str | None


class ExasolEvidenceRepository:
    def __init__(self, connection: ExasolConnection) -> None:
        self._connection = connection

    def store_evidence_and_transition(
        self,
        evidence: RegistryEvidenceRecord,
        candidate_status: CandidateStatus,
    ) -> None:
        parameters = {
            "check_id": evidence.check_id,
            "ecosystem": evidence.package.ecosystem.value,
            "registry_origin": evidence.package.registry_origin,
            "canonical_name": evidence.package.canonical_name,
            "endpoint": evidence.endpoint,
            "status": evidence.status.value,
            "http_status": evidence.http_status,
            "checked_at": evidence.checked_at,
            "response_sha256": evidence.response_sha256,
            "error_class": evidence.error_class,
            "candidate_status": candidate_status.value,
        }
        try:
            self._connection.execute(
                "INSERT INTO REGISTRY_CHECKS (CHECK_ID, ECOSYSTEM, REGISTRY_ORIGIN, "
                "CANONICAL_NAME, ENDPOINT, STATUS, HTTP_STATUS, CHECKED_AT, RESPONSE_SHA256, "
                "ERROR_CLASS) VALUES ({check_id}, {ecosystem}, {registry_origin}, "
                "{canonical_name}, {endpoint}, {status}, {http_status}, {checked_at}, "
                "{response_sha256}, {error_class})",
                parameters,
            )
            self._connection.execute(
                "MERGE INTO CANDIDATES C USING (SELECT {ecosystem} ECOSYSTEM, "
                "{registry_origin} REGISTRY_ORIGIN, {canonical_name} CANONICAL_NAME FROM DUAL) S "
                "ON C.ECOSYSTEM=S.ECOSYSTEM AND C.REGISTRY_ORIGIN=S.REGISTRY_ORIGIN "
                "AND C.CANONICAL_NAME=S.CANONICAL_NAME WHEN MATCHED THEN UPDATE SET "
                "C.STATUS={candidate_status}, C.FIRST_REGISTRATION_AT={checked_at} "
                "WHEN NOT MATCHED THEN INSERT (ECOSYSTEM, REGISTRY_ORIGIN, CANONICAL_NAME, "
                "STATUS, FIRST_REGISTRATION_AT, DISCLOSURE_CLASS, SYNTHETIC) VALUES "
                "({ecosystem}, {registry_origin}, {canonical_name}, {candidate_status}, "
                "{checked_at}, 'restricted_target_intelligence', FALSE)",
                parameters,
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise


class ExasolRadarRepository:
    def __init__(self, connection: ExasolConnection) -> None:
        self._connection = connection

    def list_private(self, *, limit: int = 100) -> list[dict[str, object]]:
        result = self._connection.execute(
            "SELECT * FROM V_RADAR_PRIVATE ORDER BY VERIFIED_MODEL_RECOMMENDATIONS DESC "
            "LIMIT {limit!d}",
            {"limit": limit},
        )
        return [{str(index): value for index, value in enumerate(row)} for row in _rows(result)]


class ExasolPolicyRepository:
    def __init__(self, connection: ExasolConnection) -> None:
        self._connection = connection

    def load_evidence(self, *, ecosystem: str, origin: str, name: str) -> dict[str, object]:
        result = self._connection.execute(
            "SELECT * FROM V_RADAR_PRIVATE WHERE ECOSYSTEM={ecosystem} "
            "AND REGISTRY_ORIGIN={origin} AND CANONICAL_NAME={name}",
            {"ecosystem": ecosystem, "origin": origin, "name": name},
        )
        rows = _rows(result)
        return {} if not rows else {str(index): value for index, value in enumerate(rows[0])}
