"""Bounded tar/sdist inspection without extracting or executing content."""

from __future__ import annotations

import tarfile
from typing import BinaryIO

from .common import seekable_size, validate_entry_path
from .models import ArchiveInspection, ArchiveLimits, UnsafeArchiveError


def inspect_tar(fileobj: BinaryIO, *, limits: ArchiveLimits) -> ArchiveInspection:
    compressed_bytes = seekable_size(fileobj)
    if compressed_bytes > limits.max_compressed_bytes:
        raise UnsafeArchiveError("compressed archive exceeds configured size limit")

    try:
        with tarfile.open(fileobj=fileobj, mode="r:*") as archive:
            expanded_bytes = 0
            entry_count = 0
            observed_paths: set[str] = set()
            for entry in archive:
                entry_count += 1
                if entry_count > limits.max_entries:
                    raise UnsafeArchiveError("archive contains too many entries")
                validate_entry_path(entry.name)
                canonical_path = entry.name.rstrip("/").casefold()
                if canonical_path in observed_paths:
                    raise UnsafeArchiveError("archive contains duplicate entry paths")
                observed_paths.add(canonical_path)
                if not (entry.isfile() or entry.isdir()):
                    raise UnsafeArchiveError("archive links and special files are not allowed")
                if entry.isfile():
                    if entry.size > limits.max_file_bytes:
                        raise UnsafeArchiveError("archive entry exceeds configured file-size limit")
                    expanded_bytes += entry.size
                    if expanded_bytes > limits.max_expanded_bytes:
                        raise UnsafeArchiveError("expanded archive exceeds configured size limit")
    except (tarfile.TarError, EOFError) as exc:
        raise UnsafeArchiveError("invalid tar archive") from exc

    if compressed_bytes and expanded_bytes / compressed_bytes > limits.max_compression_ratio:
        raise UnsafeArchiveError("archive has an unsafe compression ratio")
    return ArchiveInspection(
        format="tar",
        compressed_bytes=compressed_bytes,
        expanded_bytes=expanded_bytes,
        entry_count=entry_count,
    )
