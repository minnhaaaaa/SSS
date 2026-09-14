from __future__ import annotations

import httpx
import pytest
import respx
from sss_core.domain import Ecosystem
from sss_core.identity import canonicalize_identity
from sss_core.registries.base import RegistryOutcome
from sss_core.registries.npm import NpmRegistryOracle
from sss_core.registries.pypi import PyPIRegistryOracle


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "body", "outcome"),
    [
        (200, {"info": {"name": "demo"}}, RegistryOutcome.REGISTERED),
        (404, {"message": "not found"}, RegistryOutcome.ABSENT),
        (401, {}, RegistryOutcome.UNKNOWN_AUTH),
        (403, {}, RegistryOutcome.UNKNOWN_AUTH),
        (429, {}, RegistryOutcome.UNKNOWN_RATE_LIMIT),
        (500, {}, RegistryOutcome.UNKNOWN_SERVER),
    ],
)
async def test_pypi_registry_truth_table(
    status_code: int,
    body: dict[str, object],
    outcome: RegistryOutcome,
) -> None:
    identity = canonicalize_identity(Ecosystem.PYPI, "https://pypi.org", "demo")
    async with httpx.AsyncClient() as client:
        oracle = PyPIRegistryOracle(client, retry_delay=0)
        with respx.mock(assert_all_called=False) as router:
            route = router.get("https://pypi.org/pypi/demo/json").mock(
                return_value=httpx.Response(status_code, json=body)
            )
            evidence = await oracle.check(identity)

    assert evidence.outcome is outcome
    assert route.call_count == (3 if status_code == 429 or status_code >= 500 else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "body", "outcome"),
    [
        (200, {"name": "@scope/name", "versions": {}}, RegistryOutcome.REGISTERED),
        (404, {"error": "not_found"}, RegistryOutcome.ABSENT),
        (401, {}, RegistryOutcome.UNKNOWN_AUTH),
        (403, {}, RegistryOutcome.UNKNOWN_AUTH),
        (429, {}, RegistryOutcome.UNKNOWN_RATE_LIMIT),
        (503, {}, RegistryOutcome.UNKNOWN_SERVER),
    ],
)
async def test_npm_registry_truth_table_and_scoped_encoding(
    status_code: int,
    body: dict[str, object],
    outcome: RegistryOutcome,
) -> None:
    identity = canonicalize_identity(
        Ecosystem.NPM, "https://registry.npmjs.org", "@Scope/Name"
    )
    async with httpx.AsyncClient() as client:
        oracle = NpmRegistryOracle(client, retry_delay=0)
        with respx.mock(assert_all_called=False) as router:
            route = router.get("https://registry.npmjs.org/@scope%2Fname").mock(
                return_value=httpx.Response(status_code, json=body)
            )
            evidence = await oracle.check(identity)

    assert evidence.outcome is outcome
    assert route.call_count == (3 if status_code == 429 or status_code >= 500 else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [httpx.ConnectError("dns/tls failure"), httpx.TimeoutException("timed out")],
)
async def test_network_failures_remain_unknown(error: httpx.HTTPError) -> None:
    identity = canonicalize_identity(Ecosystem.PYPI, "https://pypi.org", "demo")
    async with httpx.AsyncClient() as client:
        oracle = PyPIRegistryOracle(client, retry_delay=0)
        with respx.mock(assert_all_called=False) as router:
            route = router.get("https://pypi.org/pypi/demo/json").mock(side_effect=error)
            evidence = await oracle.check(identity)

    assert evidence.outcome is RegistryOutcome.UNKNOWN_NETWORK
    assert route.call_count == 3


@pytest.mark.asyncio
async def test_malformed_success_response_remains_unknown() -> None:
    identity = canonicalize_identity(Ecosystem.NPM, "https://registry.npmjs.org", "demo")
    async with httpx.AsyncClient() as client:
        oracle = NpmRegistryOracle(client, retry_delay=0)
        with respx.mock as router:
            router.get("https://registry.npmjs.org/demo").mock(
                return_value=httpx.Response(200, content=b"not-json")
            )
            evidence = await oracle.check(identity)

    assert evidence.outcome is RegistryOutcome.UNKNOWN_RESPONSE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ecosystem", "name", "url", "body", "oracle_type"),
    [
        (
            Ecosystem.PYPI,
            "demo",
            "https://pypi.org/pypi/demo/json",
            {
                "info": {"name": "demo"},
                "releases": {"1.0": [{"upload_time_iso_8601": "2026-08-30T12:00:00Z"}]},
            },
            PyPIRegistryOracle,
        ),
        (
            Ecosystem.NPM,
            "demo",
            "https://registry.npmjs.org/demo",
            {
                "name": "demo",
                "versions": {"1.0.0": {}},
                "time": {"1.0.0": "2026-08-30T12:00:00.000Z"},
            },
            NpmRegistryOracle,
        ),
    ],
)
async def test_registered_metadata_captures_first_release_time(
    ecosystem: Ecosystem,
    name: str,
    url: str,
    body: dict[str, object],
    oracle_type: type[PyPIRegistryOracle] | type[NpmRegistryOracle],
) -> None:
    origin = "https://pypi.org" if ecosystem is Ecosystem.PYPI else "https://registry.npmjs.org"
    identity = canonicalize_identity(ecosystem, origin, name)
    async with httpx.AsyncClient() as client:
        oracle = oracle_type(client, retry_delay=0)
        with respx.mock:
            respx.get(url).mock(return_value=httpx.Response(200, json=body))
            evidence = await oracle.check(identity)

    assert evidence.first_release_at is not None
    assert evidence.first_release_at.isoformat() == "2026-08-30T12:00:00+00:00"


def test_alternate_registry_is_part_of_identity() -> None:
    public = canonicalize_identity(Ecosystem.NPM, "https://registry.npmjs.org", "demo")
    private = canonicalize_identity(Ecosystem.NPM, "https://npm.example.invalid", "demo")

    assert public != private
