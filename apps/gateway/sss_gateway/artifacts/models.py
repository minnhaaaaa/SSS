"""Immutable archive inspection inputs and outputs."""

from __future__ import annotations

from dataclasses import dataclass


class UnsafeArchiveError(ValueError):
    """Raised when an archive violates a bounded static safety rule."""


@dataclass(frozen=True, slots=True)
class ArchiveLimits:
    max_compressed_bytes: int
    max_expanded_bytes: int
    max_entries: int
    max_file_bytes: int
    max_compression_ratio: float

    def __post_init__(self) -> None:
        values = (
            self.max_compressed_bytes,
            self.max_expanded_bytes,
            self.max_entries,
            self.max_file_bytes,
            self.max_compression_ratio,
        )
        if any(value <= 0 for value in values):
            raise ValueError("archive limits must be positive")


@dataclass(frozen=True, slots=True)
class ArchiveInspection:
    format: str
    compressed_bytes: int
    expanded_bytes: int
    entry_count: int
