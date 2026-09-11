"""Transactional SQLite persistence for observable canary events."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock


@dataclass(frozen=True, slots=True)
class CanaryEvent:
    event_id: int
    marker: str
    occurred_at: str


class CanaryRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._lock = Lock()

    def initialize(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS CANARY_EVENTS (
                    EVENT_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    MARKER TEXT NOT NULL,
                    OCCURRED_AT TEXT NOT NULL
                )
                """
            )

    def record(self, marker: str) -> CanaryEvent:
        occurred_at = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO CANARY_EVENTS (MARKER, OCCURRED_AT) VALUES (?, ?)",
                (marker, occurred_at),
            )
            event_id = cursor.lastrowid
            if event_id is None:
                raise RuntimeError("SQLite did not return a canary event ID")
        return CanaryEvent(event_id=event_id, marker=marker, occurred_at=occurred_at)

    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM CANARY_EVENTS").fetchone()
        if row is None:
            raise RuntimeError("canary count query returned no row")
        return int(row[0])

    def reset(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM CANARY_EVENTS")
            connection.execute("DELETE FROM sqlite_sequence WHERE name = 'CANARY_EVENTS'")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._database_path, timeout=5)
