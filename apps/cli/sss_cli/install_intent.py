"""Package-manager argument parsing shared by CLI commands and executable shims."""

from __future__ import annotations

import hashlib
import re
import shlex
from collections.abc import Sequence

from sss_core import Ecosystem, InstallRequest
from sss_core.extraction import ExtractedPackage, PackageSource, UnsafeInputError
from sss_core.extraction.npm import extract_npm_mentions
from sss_core.extraction.python import extract_python_mentions
from sss_core.identity import canonicalize_identity

_EXACT_NPM_VERSION = re.compile(
    r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$"
)
_EXACT_PYTHON_VERSION = re.compile(r"^===?[^,;*~!<>=\s]+$")
_SHELL_TOKENS = frozenset({";", "&&", "||", "|", ">", ">>", "<", "<<"})


def parse_install_argv(
    manager: str,
    arguments: Sequence[str],
    *,
    registry_origin: str,
    project_id: str,
    agent_family: str,
    artifact_sha256: str | None,
    pypi_registry_origin: str = "https://pypi.org",
) -> tuple[InstallRequest, ...]:
    """Convert a supported install argv into exact, policy-ready requests."""

    normalized_manager = manager.casefold()
    argv = tuple(arguments)
    if any(_unsafe_argument(argument) for argument in argv):
        raise ValueError("package-manager arguments contain unsafe shell syntax")
    if artifact_sha256 is not None and (
        len(artifact_sha256) != 64 or any(c not in "0123456789abcdef" for c in artifact_sha256)
    ):
        raise ValueError("install assessment requires a lowercase SHA-256")
    command = shlex.join((normalized_manager, *argv))
    try:
        if normalized_manager in {"npm", "pnpm", "yarn", "npx"}:
            mentions = extract_npm_mentions(command)
            expected_origin = registry_origin
        elif normalized_manager in {"pip", "pip3", "python", "python3", "uv"}:
            mentions = extract_python_mentions(command)
            expected_origin = pypi_registry_origin
        else:
            raise ValueError(f"unsupported package manager: {manager}")
    except UnsafeInputError as exc:
        raise ValueError("package-manager arguments contain unsafe shell syntax") from exc
    if not mentions:
        raise ValueError(f"{manager} command does not contain supported install intent")

    requests: list[InstallRequest] = []
    for mention in mentions:
        _require_registry_source(mention)
        _require_exact_version(mention)
        package = canonicalize_identity(
            mention.ecosystem,
            expected_origin,
            mention.canonical_name,
        )
        request_key = "\0".join(
            (
                project_id,
                agent_family,
                normalized_manager,
                *argv,
                package.registry_origin,
                package.canonical_name,
                mention.version_spec or "",
                artifact_sha256 or "",
            )
        )
        requests.append(
            InstallRequest(
                request_id=hashlib.sha256(request_key.encode()).hexdigest(),
                project_id=project_id,
                agent_family=agent_family,
                package=package,
                version_spec=mention.version_spec,
                direct_url=None,
                artifact_sha256=artifact_sha256,
                is_direct=True,
            )
        )
    return tuple(requests)


def _require_registry_source(mention: ExtractedPackage) -> None:
    if mention.source is not PackageSource.REGISTRY or mention.requested_registry is not None:
        raise ValueError("only the configured registry is allowed")


def _require_exact_version(mention: ExtractedPackage) -> None:
    version = mention.version_spec or ""
    if mention.ecosystem is Ecosystem.NPM:
        exact = _EXACT_NPM_VERSION.fullmatch(version) is not None
    else:
        exact = _EXACT_PYTHON_VERSION.fullmatch(version) is not None
    if not exact:
        raise ValueError("strict mode requires an exact package version")


def _unsafe_argument(argument: str) -> bool:
    return (
        not argument
        or argument in _SHELL_TOKENS
        or "\x00" in argument
        or "\r" in argument
        or "\n" in argument
        or "$(" in argument
        or "`" in argument
    )
