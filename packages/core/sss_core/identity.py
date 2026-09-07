from __future__ import annotations

import re
from urllib.parse import SplitResult, urlsplit, urlunsplit

from packaging.utils import canonicalize_name

from sss_core.domain import Ecosystem, PackageIdentity

_NPM_NAME = re.compile(
    r"^(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*$",
    flags=re.ASCII,
)
_PYPI_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$", flags=re.ASCII)


class IdentityValidationError(ValueError):
    """Raised when a registry origin or package name is not a safe identity."""


def _canonicalize_registry_origin(ecosystem: Ecosystem, origin: str) -> str:
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.hostname:
        raise IdentityValidationError("registry origin must be an absolute https URL")
    if parsed.username is not None or parsed.password is not None:
        raise IdentityValidationError("registry origin must not contain credentials")
    if parsed.query or parsed.fragment:
        raise IdentityValidationError("registry origin must not contain a query or fragment")

    allowed_paths = {"", "/"}
    if ecosystem is Ecosystem.PYPI:
        allowed_paths.update({"/simple", "/simple/"})
    if parsed.path not in allowed_paths:
        raise IdentityValidationError("registry URL must identify an origin, not a nested path")

    host = parsed.hostname.lower()
    try:
        port = parsed.port
    except ValueError as error:
        raise IdentityValidationError("registry origin contains an invalid port") from error
    netloc = f"{host}:{port}" if port is not None else host
    return urlunsplit(SplitResult("https", netloc, "", "", ""))


def _canonicalize_package_name(ecosystem: Ecosystem, name: str) -> str:
    if ecosystem is Ecosystem.PYPI:
        if len(name) > 100 or not _PYPI_NAME.fullmatch(name):
            raise IdentityValidationError("invalid PyPI distribution name")
        return str(canonicalize_name(name))

    canonical_name = name.lower()
    if len(canonical_name) > 214 or not _NPM_NAME.fullmatch(canonical_name):
        raise IdentityValidationError("invalid npm package name")
    if name != canonical_name and not name.startswith("@"):
        raise IdentityValidationError("unscoped npm package names must be lowercase")
    return canonical_name


def canonicalize_identity(
    ecosystem: Ecosystem,
    origin: str,
    name: str,
) -> PackageIdentity:
    """Return the canonical cross-ecosystem package identity."""

    return PackageIdentity(
        ecosystem=ecosystem,
        registry_origin=_canonicalize_registry_origin(ecosystem, origin),
        canonical_name=_canonicalize_package_name(ecosystem, name),
    )
