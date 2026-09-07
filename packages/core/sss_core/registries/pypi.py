from __future__ import annotations

from datetime import datetime

import httpx
from packaging.utils import canonicalize_name

from sss_core.domain import Ecosystem, PackageIdentity
from sss_core.registries._http import HttpRegistryOracle


def _endpoint(identity: PackageIdentity) -> str:
    if identity.ecosystem is not Ecosystem.PYPI:
        raise ValueError("PyPI oracle only accepts PyPI identities")
    return f"{identity.registry_origin}/pypi/{identity.canonical_name}/json"


def _valid_metadata(identity: PackageIdentity, payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    info = payload.get("info")
    return (
        isinstance(info, dict)
        and isinstance(info.get("name"), str)
        and canonicalize_name(info["name"]) == identity.canonical_name
    )


def _first_release_at(payload: object) -> datetime | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("releases"), dict):
        return None
    timestamps: list[datetime] = []
    for files in payload["releases"].values():
        if not isinstance(files, list):
            continue
        for file_metadata in files:
            if not isinstance(file_metadata, dict):
                continue
            value = file_metadata.get("upload_time_iso_8601")
            if not isinstance(value, str):
                continue
            try:
                timestamps.append(datetime.fromisoformat(value.replace("Z", "+00:00")))
            except ValueError:
                continue
    return min(timestamps) if timestamps else None


class PyPIRegistryOracle(HttpRegistryOracle):
    def __init__(self, client: httpx.AsyncClient, *, retry_delay: float = 0.1) -> None:
        super().__init__(
            client,
            endpoint_for=_endpoint,
            valid_metadata=_valid_metadata,
            first_release_at=_first_release_at,
            retry_delay=retry_delay,
        )
