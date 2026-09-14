from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sss_core.domain import CandidateStatus, Ecosystem, RegistryStatus
from sss_core.identity import canonicalize_identity
from sss_core.registries.base import RegistryEvidence, RegistryOutcome
from sss_worker.jobs.recheck import MemoryRecheckSink, TransitionDetector, recheck_watchlist


def test_later_registration_creates_transition_without_mutating_absence() -> None:
    identity = canonicalize_identity(Ecosystem.NPM, "https://registry.npmjs.org", "demo")
    first_time = datetime(2026, 8, 27, tzinfo=UTC)
    original = RegistryEvidence(
        package=identity,
        endpoint="https://registry.npmjs.org/demo",
        outcome=RegistryOutcome.ABSENT,
        registry_status=RegistryStatus.ABSENT,
        http_status=404,
        checked_at=first_time,
        response_sha256="a" * 64,
        error_class=None,
    )
    later = RegistryEvidence(
        package=identity,
        endpoint="https://registry.npmjs.org/demo",
        outcome=RegistryOutcome.REGISTERED,
        registry_status=RegistryStatus.REGISTERED,
        http_status=200,
        checked_at=first_time + timedelta(days=11),
        response_sha256="b" * 64,
        error_class=None,
        first_release_at=first_time + timedelta(days=10),
    )

    result = TransitionDetector().detect(original, later)

    assert result.status is CandidateStatus.REGISTERED_AFTER_ABSENCE
    assert result.historical_absence is original
    assert result.registration is later
    assert original.response_sha256 == "a" * 64


def test_registration_predating_absence_is_not_a_transition() -> None:
    identity = canonicalize_identity(Ecosystem.NPM, "https://registry.npmjs.org", "demo")
    absence_time = datetime(2026, 8, 27, tzinfo=UTC)
    original = RegistryEvidence(
        identity,
        "https://registry.npmjs.org/demo",
        RegistryOutcome.ABSENT,
        RegistryStatus.ABSENT,
        404,
        absence_time,
        "a" * 64,
        None,
    )
    pre_existing = RegistryEvidence(
        identity,
        "https://registry.npmjs.org/demo",
        RegistryOutcome.REGISTERED,
        RegistryStatus.REGISTERED,
        200,
        absence_time + timedelta(days=1),
        "b" * 64,
        None,
        first_release_at=absence_time - timedelta(days=30),
    )

    result = TransitionDetector().detect(original, pre_existing)

    assert result.status is CandidateStatus.REGISTERED
    assert result.registration is pre_existing


def test_inconclusive_recheck_retains_absence_without_registration() -> None:
    identity = canonicalize_identity(Ecosystem.NPM, "https://registry.npmjs.org", "demo")
    absence_time = datetime(2026, 8, 27, tzinfo=UTC)
    original = RegistryEvidence(
        identity,
        "https://registry.npmjs.org/demo",
        RegistryOutcome.ABSENT,
        RegistryStatus.ABSENT,
        404,
        absence_time,
        "a" * 64,
        None,
    )
    unknown = RegistryEvidence(
        identity,
        "https://registry.npmjs.org/demo",
        RegistryOutcome.UNKNOWN_NETWORK,
        RegistryStatus.UNKNOWN,
        None,
        absence_time + timedelta(hours=1),
        None,
        "TimeoutException",
    )

    result = TransitionDetector().detect(original, unknown)

    assert result.status is CandidateStatus.VERIFIED_ABSENT
    assert result.historical_absence is original
    assert result.registration is None


@pytest.mark.asyncio
async def test_recheck_watchlist_deduplicates_identity_and_persists_result() -> None:
    identity = canonicalize_identity(Ecosystem.NPM, "https://registry.npmjs.org", "demo")
    checked_at = datetime(2026, 9, 7, tzinfo=UTC)
    evidence = RegistryEvidence(
        identity,
        "https://registry.npmjs.org/demo",
        RegistryOutcome.ABSENT,
        RegistryStatus.ABSENT,
        404,
        checked_at,
        "a" * 64,
        None,
    )

    class Oracle:
        def __init__(self) -> None:
            self.calls = 0

        async def check(self, package: object) -> RegistryEvidence:
            assert package == identity
            self.calls += 1
            return evidence

    oracle = Oracle()
    sink = MemoryRecheckSink()

    first = await recheck_watchlist([identity, identity], {Ecosystem.NPM: oracle}, sink)
    second = await recheck_watchlist([identity], {Ecosystem.NPM: oracle}, sink)

    assert first == 1
    assert second == 0
    assert oracle.calls == 2
    assert sink.evidence == {"a" * 64: evidence}
