from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

from packaging.utils import canonicalize_name


@dataclass(frozen=True)
class BaselineSnapshot:
    content: bytes
    sha256: str
    project_count: int
    normalization_version: str


class BaselineBuilder:
    def __init__(self, *, normalization_version: str) -> None:
        self._normalization_version = normalization_version

    def build(self, projects: Iterable[str]) -> BaselineSnapshot:
        canonical_projects = sorted({str(canonicalize_name(project)) for project in projects})
        content = ("\n".join(canonical_projects) + "\n").encode()
        return BaselineSnapshot(
            content=content,
            sha256=hashlib.sha256(content).hexdigest(),
            project_count=len(canonical_projects),
            normalization_version=self._normalization_version,
        )
