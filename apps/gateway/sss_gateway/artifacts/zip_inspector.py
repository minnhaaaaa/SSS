"""Bounded ZIP/wheel inspection without extracting or executing content."""

from __future__ import annotations

import stat
import zipfile
from typing import BinaryIO

from .common import seekable_size, validate_entry_path
from .models import ArchiveInspection, ArchiveLimits, UnsafeArchiveError


def inspect_zip(fileobj: BinaryIO, *, limits: ArchiveLimits) -> ArchiveInspection:
    compressed_bytes = seekable_size(fileobj)
    if compressed_bytes > limits.max_compressed_bytes:
        raise UnsafeArchiveError("compressed archive exceeds configured size limit")

    try:
        with zipfile.ZipFile(fileobj) as archive:
            entries = archive.infolist()
            if len(entries) > limits.max_entries:
                raise UnsafeArchiveError("archive contains too many entries")
            expanded_bytes = 0
            observed_paths: set[str] = set()
            for entry in entries:
                validate_entry_path(entry.filename)
                canonical_path = entry.filename.rstrip("/").casefold()
                if canonical_path in observed_paths:
                    raise UnsafeArchiveError("archive contains duplicate entry paths")
                observed_paths.add(canonical_path)
                _validate_zip_entry(entry, limits=limits)
                if not entry.is_dir():
                    expanded_bytes += entry.file_size
                    if expanded_bytes > limits.max_expanded_bytes:
                        raise UnsafeArchiveError("expanded archive exceeds configured size limit")
    except (zipfile.BadZipFile, EOFError) as exc:
        raise UnsafeArchiveError("invalid ZIP archive") from exc

    return ArchiveInspection(
        format="zip",
        compressed_bytes=compressed_bytes,
        expanded_bytes=expanded_bytes,
        entry_count=len(entries),
    )


def _validate_zip_entry(entry: zipfile.ZipInfo, *, limits: ArchiveLimits) -> None:
    if entry.flag_bits & 0x1:
        raise UnsafeArchiveError("encrypted archive entries cannot be inspected")
    unix_mode = (entry.external_attr >> 16) & 0xFFFF
    if unix_mode and stat.S_ISLNK(unix_mode):
        raise UnsafeArchiveError("archive links are not allowed")
    file_type = stat.S_IFMT(unix_mode)
    if file_type and file_type not in {stat.S_IFREG, stat.S_IFDIR}:
        raise UnsafeArchiveError("archive special files are not allowed")
    if entry.is_dir():
        return
    if entry.file_size > limits.max_file_bytes:
        raise UnsafeArchiveError("archive entry exceeds configured file-size limit")
    if entry.file_size:
        if entry.compress_size == 0:
            raise UnsafeArchiveError("archive entry has an unsafe compression ratio")
        ratio = entry.file_size / entry.compress_size
        if ratio > limits.max_compression_ratio:
            raise UnsafeArchiveError("archive entry has an unsafe compression ratio")
