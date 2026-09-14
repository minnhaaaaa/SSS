from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

import httpx

from sss_core.domain import Ecosystem, PackageIdentity
from sss_core.registries._http import HttpRegistryOracle


def _endpoint(identity: PackageIdentity) -> str:
    if identity.ecosystem is not Ecosystem.NPM:
        raise ValueError("npm oracle only accepts npm identities")
    encoded_name = quote(identity.canonical_name, safe="@")
    return f"{identity.registry_origin}/{encoded_name}"


def _valid_metadata(identity: PackageIdentity, payload: object) -> bool:
    return (
        isinstance(payload, dict)
        and isinstance(payload.get("name"), str)
        and payload["name"].lower() == identity.canonical_name
        and isinstance(payload.get("versions"), dict)
    )


def _first_release_at(payload: object) -> datetime | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("time"), dict):
        return None
    timestamps: list[datetime] = []
    for version, value in payload["time"].items():
        if version in {"created", "modified"} or not isinstance(value, str):
            continue
        try:
            timestamps.append(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            continue
    return min(timestamps) if timestamps else None


class NpmRegistryOracle(HttpRegistryOracle):
    def __init__(self, client: httpx.AsyncClient, *, retry_delay: float = 0.1) -> None:
        super().__init__(
            client,
            endpoint_for=_endpoint,
            valid_metadata=_valid_metadata,
            first_release_at=_first_release_at,
            retry_delay=retry_delay,
        )
