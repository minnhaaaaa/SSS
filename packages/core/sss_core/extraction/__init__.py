from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sss_core.domain import Ecosystem


class PackageSource(StrEnum):
    REGISTRY = "registry"
    ALTERNATE_REGISTRY = "alternate_registry"
    IMPORT = "import"
    ALIAS = "alias"
    DIRECT_URL = "direct_url"
    VCS = "vcs"
    LOCAL_PATH = "local_path"


class UnsafeInputError(ValueError):
    """Raised when text contains shell syntax that must never be evaluated."""


@dataclass(frozen=True)
class ExtractedPackage:
    ecosystem: Ecosystem
    raw: str
    canonical_name: str
    version_spec: str | None
    source: PackageSource
    is_direct: bool = True
    requested_registry: str | None = None
