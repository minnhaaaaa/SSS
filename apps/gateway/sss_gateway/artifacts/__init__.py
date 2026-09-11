"""Non-executing archive safety inspection."""

from .models import ArchiveInspection, ArchiveLimits, UnsafeArchiveError
from .tar_inspector import inspect_tar
from .zip_inspector import inspect_zip

__all__ = [
    "ArchiveInspection",
    "ArchiveLimits",
    "UnsafeArchiveError",
    "inspect_tar",
    "inspect_zip",
]
