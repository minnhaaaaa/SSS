from __future__ import annotations

from sss_core.domain import EvidenceProvenance
from sss_worker.jobs.github import GitHubArtifact, GitHubPage, scan_public_sources
from sss_worker.jobs.probe import MemoryObservationSink


def test_collects_manifest_and_conclusive_failure_but_rejects_prose() -> None:
    sink = MemoryObservationSink()
    page = GitHubPage(
        cursor="page-1",
        next_cursor="page-2",
        artifacts=(
            GitHubArtifact(
                repository="org/project",
                path="package.json",
                url="https://github.com/org/project/blob/main/package.json",
                content='{"dependencies":{"missing-widget":"^1"}}',
            ),
            GitHubArtifact(
                repository="org/project",
                path="ci.log",
                url="https://github.com/org/project/actions/runs/1",
                content="npm ERR! 404 Not Found - GET registry/missing-widget",
            ),
            GitHubArtifact(
                repository="org/project",
                path="README.md",
                url="https://github.com/org/project/blob/main/README.md",
                content="Maybe someday we could name a package missing-widget.",
            ),
        ),
    )

    result = scan_public_sources(page, sink)

    assert result.new_mentions == 2
    assert sink.cursor("github") == "page-2"
    assert {item.provenance for item in sink.observations.values()} == {
        EvidenceProvenance.PUBLIC_MANIFEST,
        EvidenceProvenance.PUBLIC_CI_FAILURE,
    }


def test_rate_limit_retains_cursor_and_deletion_is_recorded() -> None:
    sink = MemoryObservationSink()
    sink.save_cursor("github", "page-7")

    limited = scan_public_sources(
        GitHubPage(cursor="page-7", next_cursor="page-8", artifacts=(), rate_limited=True),
        sink,
    )
    assert sink.cursor("github") == "page-7"

    deleted = GitHubArtifact(
        repository="org/project",
        path="requirements.txt",
        url="https://github.com/org/project/blob/main/requirements.txt",
        content="",
        deleted=True,
    )
    scan_public_sources(
        GitHubPage(cursor="page-7", next_cursor="page-8", artifacts=(deleted,)),
        sink,
    )

    assert limited.rate_limited
    assert sink.cursor("github") == "page-8"
    assert sink.deletions == {"org/project:requirements.txt"}


def test_one_public_source_cannot_inflate_recurrence() -> None:
    sink = MemoryObservationSink()
    artifact = GitHubArtifact(
        repository="org/project",
        path="requirements.txt",
        url="https://github.com/org/project/blob/main/requirements.txt",
        content="missing-helper==1",
    )
    page = GitHubPage(cursor=None, next_cursor=None, artifacts=(artifact, artifact, artifact))

    scan_public_sources(page, sink)

    assert sink.recurrence_count("pypi", "missing-helper") == 1
