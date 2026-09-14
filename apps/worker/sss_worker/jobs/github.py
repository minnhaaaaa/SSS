from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from sss_core.domain import Ecosystem, EvidenceProvenance
from sss_core.extraction.npm import extract_npm_mentions
from sss_core.extraction.python import extract_python_mentions

from sss_worker.jobs.probe import CollectedObservation, CollectionResult, make_observation

_NPM_NOT_FOUND = re.compile(r"404 Not Found - GET \S+/(@?[^/\s]+(?:/[^/\s]+)?)", re.IGNORECASE)
_PYPI_NOT_FOUND = re.compile(r"No matching distribution found for ([A-Za-z0-9._-]+)")


@dataclass(frozen=True)
class GitHubArtifact:
    repository: str
    path: str
    url: str
    content: str
    deleted: bool = False

    @property
    def source_id(self) -> str:
        return f"{self.repository}:{self.path}"


@dataclass(frozen=True)
class GitHubPage:
    cursor: str | None
    next_cursor: str | None
    artifacts: tuple[GitHubArtifact, ...]
    rate_limited: bool = False


class PublicSourceSink(Protocol):
    def record(self, observation: CollectedObservation) -> bool: ...
    def record_deletion(self, source_id: str) -> None: ...
    def save_cursor(self, source: str, cursor: str | None) -> None: ...


def _manifest_mentions(artifact: GitHubArtifact) -> tuple[tuple[Ecosystem, str], ...]:
    filename = artifact.path.rsplit("/", maxsplit=1)[-1]
    if filename in {"package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"}:
        return tuple(
            (Ecosystem.NPM, mention.canonical_name)
            for mention in extract_npm_mentions(artifact.content)
        )
    if filename.startswith("requirements") or filename == "pyproject.toml":
        return tuple(
            (Ecosystem.PYPI, mention.canonical_name)
            for mention in extract_python_mentions(artifact.content)
        )
    return ()


def _failure_mentions(artifact: GitHubArtifact) -> tuple[tuple[Ecosystem, str], ...]:
    npm = _NPM_NOT_FOUND.search(artifact.content)
    if npm:
        return ((Ecosystem.NPM, npm.group(1).lower()),)
    pypi = _PYPI_NOT_FOUND.search(artifact.content)
    if pypi:
        return ((Ecosystem.PYPI, pypi.group(1).lower().replace("_", "-")),)
    return ()


def scan_public_sources(
    page: GitHubPage,
    sink: PublicSourceSink,
) -> CollectionResult:
    if page.rate_limited:
        return CollectionResult(0, rate_limited=True)
    new_mentions = 0
    for artifact in page.artifacts:
        if artifact.deleted:
            sink.record_deletion(artifact.source_id)
            continue
        mentions = _manifest_mentions(artifact)
        provenance = EvidenceProvenance.PUBLIC_MANIFEST
        if not mentions:
            mentions = _failure_mentions(artifact)
            provenance = EvidenceProvenance.PUBLIC_CI_FAILURE
        for ecosystem, name in mentions:
            new_mentions += sink.record(
                make_observation(
                    provenance=provenance,
                    source_id=artifact.source_id,
                    ecosystem=ecosystem,
                    canonical_name=name,
                )
            )
    sink.save_cursor("github", page.next_cursor)
    return CollectionResult(new_mentions)
