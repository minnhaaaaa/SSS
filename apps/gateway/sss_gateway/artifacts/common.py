"""Safety checks shared by supported archive formats."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import BinaryIO

from .models import UnsafeArchiveError


def validate_entry_path(name: str) -> None:
    if not name or "\\" in name or "\x00" in name:
        raise UnsafeArchiveError("archive entry has an invalid path")
    normalized_name = name[:-1] if name.endswith("/") else name
    raw_parts = normalized_name.split("/")
    path = PurePosixPath(normalized_name)
    if (
        not normalized_name
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in raw_parts)
    ):
        raise UnsafeArchiveError("archive entry escapes its extraction root")
    if path.parts and len(path.parts[0]) >= 2 and path.parts[0][1] == ":":
        raise UnsafeArchiveError("archive entry uses an absolute drive path")


def seekable_size(fileobj: BinaryIO) -> int:
    if not fileobj.seekable():
        raise UnsafeArchiveError("archive input must be seekable for bounded inspection")
    original = fileobj.tell()
    fileobj.seek(0, 2)
    size = fileobj.tell()
    fileobj.seek(original)
    return size
