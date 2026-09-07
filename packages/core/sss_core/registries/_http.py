from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from sss_core.domain import PackageIdentity, RegistryStatus
from sss_core.registries.base import RegistryEvidence, RegistryOutcome


class HttpRegistryOracle:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        endpoint_for: Callable[[PackageIdentity], str],
        valid_metadata: Callable[[PackageIdentity, object], bool],
        first_release_at: Callable[[object], datetime | None],
        retry_delay: float,
    ) -> None:
        self._client = client
        self._endpoint_for = endpoint_for
        self._valid_metadata = valid_metadata
        self._first_release_at = first_release_at
        self._retry_delay = retry_delay

    async def check(self, identity: PackageIdentity) -> RegistryEvidence:
        endpoint = self._endpoint_for(identity)
        for attempt in range(3):
            try:
                response = await self._client.get(endpoint)
            except (httpx.ConnectError, httpx.TimeoutException) as error:
                if attempt < 2:
                    await asyncio.sleep(self._retry_delay)
                    continue
                return self._unknown(
                    identity, endpoint, RegistryOutcome.UNKNOWN_NETWORK, None, type(error).__name__
                )

            response_hash = hashlib.sha256(response.content).hexdigest()
            if response.status_code == 404:
                return RegistryEvidence(
                    identity,
                    endpoint,
                    RegistryOutcome.ABSENT,
                    RegistryStatus.ABSENT,
                    404,
                    datetime.now(UTC),
                    response_hash,
                    None,
                )
            if response.status_code in {401, 403}:
                return self._unknown(
                    identity,
                    endpoint,
                    RegistryOutcome.UNKNOWN_AUTH,
                    response.status_code,
                    "http_auth",
                    response_hash,
                )
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 2:
                    await asyncio.sleep(self._retry_delay)
                    continue
                outcome = (
                    RegistryOutcome.UNKNOWN_RATE_LIMIT
                    if response.status_code == 429
                    else RegistryOutcome.UNKNOWN_SERVER
                )
                return self._unknown(
                    identity,
                    endpoint,
                    outcome,
                    response.status_code,
                    "http_retry_exhausted",
                    response_hash,
                )
            if response.status_code != 200:
                return self._unknown(
                    identity,
                    endpoint,
                    RegistryOutcome.UNKNOWN_RESPONSE,
                    response.status_code,
                    "unexpected_http_status",
                    response_hash,
                )
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if not self._valid_metadata(identity, payload):
                return self._unknown(
                    identity,
                    endpoint,
                    RegistryOutcome.UNKNOWN_RESPONSE,
                    200,
                    "malformed_metadata",
                    response_hash,
                )
            return RegistryEvidence(
                identity,
                endpoint,
                RegistryOutcome.REGISTERED,
                RegistryStatus.REGISTERED,
                200,
                datetime.now(UTC),
                response_hash,
                None,
                self._first_release_at(payload),
            )
        raise AssertionError("retry loop must return")

    @staticmethod
    def _unknown(
        identity: PackageIdentity,
        endpoint: str,
        outcome: RegistryOutcome,
        http_status: int | None,
        error_class: str,
        response_sha256: str | None = None,
    ) -> RegistryEvidence:
        return RegistryEvidence(
            identity,
            endpoint,
            outcome,
            RegistryStatus.UNKNOWN,
            http_status,
            datetime.now(UTC),
            response_sha256,
            error_class,
        )
