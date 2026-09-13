from __future__ import annotations

import json
import re
import shlex
from typing import Any
from urllib.parse import urlsplit

import yaml

from sss_core.domain import Ecosystem
from sss_core.extraction import ExtractedPackage, PackageSource
from sss_core.extraction._safety import reject_shell_operators


def _split_registry_spec(spec: str) -> tuple[str, str | None]:
    if spec.startswith("@"):
        slash = spec.find("/")
        version_at = spec.find("@", slash)
        if version_at >= 0:
            return spec[:version_at].lower(), spec[version_at + 1 :] or None
        return spec.lower(), None
    if "@" in spec:
        name, version = spec.split("@", maxsplit=1)
        return name.lower(), version or None
    return spec.lower(), None


def _classify_spec(
    spec: str,
    *,
    requested_registry: str | None = None,
) -> ExtractedPackage:
    if spec.startswith(("git+", "git://", "git@", "github:")) or "github.com/" in spec:
        source = PackageSource.VCS
        name, version = spec, None
    elif spec.startswith(("./", "../", "/", "file:")):
        source = PackageSource.LOCAL_PATH
        name, version = spec, None
    elif spec.startswith(("http://", "https://")):
        source = PackageSource.DIRECT_URL
        name, version = spec, None
    elif "@npm:" in spec:
        source = PackageSource.ALIAS
        name, version = _split_registry_spec(spec.split("@npm:", maxsplit=1)[0])
    else:
        source = (
            PackageSource.ALTERNATE_REGISTRY
            if requested_registry is not None
            else PackageSource.REGISTRY
        )
        name, version = _split_registry_spec(spec)
    return ExtractedPackage(
        ecosystem=Ecosystem.NPM,
        raw=spec,
        canonical_name=name,
        version_spec=version,
        source=source,
        requested_registry=requested_registry,
    )


def _parse_manifest(text: str) -> list[ExtractedPackage]:
    try:
        document: Any = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(document, dict):
        return []
    packages = document.get("packages")
    if isinstance(packages, dict):
        root = packages.get("", {})
        document = root if isinstance(root, dict) else {}

    mentions: list[ExtractedPackage] = []
    for field in ("dependencies", "devDependencies", "optionalDependencies"):
        dependencies = document.get(field, {})
        if not isinstance(dependencies, dict):
            continue
        for name in sorted(dependencies):
            version = dependencies[name]
            if isinstance(name, str) and isinstance(version, str):
                mentions.append(_classify_spec(f"{name}@{version}"))
    return mentions


def _parse_pnpm_lock(text: str) -> list[ExtractedPackage]:
    try:
        document: Any = yaml.safe_load(text)
    except yaml.YAMLError:
        return []
    if not isinstance(document, dict) or "lockfileVersion" not in document:
        return []
    importers = document.get("importers", {})
    root = importers.get(".", {}) if isinstance(importers, dict) else {}
    if not isinstance(root, dict):
        return []
    mentions: list[ExtractedPackage] = []
    for field in ("dependencies", "devDependencies", "optionalDependencies"):
        dependencies = root.get(field, {})
        if not isinstance(dependencies, dict):
            continue
        for name in sorted(dependencies):
            value = dependencies[name]
            specifier = value.get("specifier") if isinstance(value, dict) else value
            if isinstance(name, str) and isinstance(specifier, str):
                mentions.append(_classify_spec(f"{name}@{specifier}"))
    return mentions


def _parse_yarn_lock(text: str) -> list[ExtractedPackage]:
    mentions: list[ExtractedPackage] = []
    for line in text.splitlines():
        if line.startswith((" ", "#")) or not line.endswith(":"):
            continue
        selector = line[:-1].strip('"')
        if "," in selector:
            selector = selector.split(",", maxsplit=1)[0].strip()
        if re.fullmatch(r"(?:@[^/]+/[^@]+|[^@]+)@.+", selector):
            mentions.append(_classify_spec(selector))
    return mentions


def _registry_from_argv(argv: list[str]) -> str | None:
    for index, value in enumerate(argv):
        if value == "--registry" and index + 1 < len(argv):
            candidate = argv[index + 1]
        elif value.startswith("--registry="):
            candidate = value.split("=", maxsplit=1)[1]
        else:
            continue
        parsed = urlsplit(candidate)
        if (
            parsed.scheme == "https"
            and parsed.hostname
            and not parsed.username
            and not parsed.fragment
        ):
            return candidate.rstrip("/")
    return None


def _parse_commands(text: str) -> list[ExtractedPackage]:
    mentions: list[ExtractedPackage] = []
    for line in text.splitlines():
        try:
            argv = shlex.split(line.strip())
        except ValueError:
            continue
        start: int | None = None
        if len(argv) >= 2 and (
            (argv[0] == "npm" and argv[1] in {"install", "i"})
            or (argv[0] in {"pnpm", "yarn"} and argv[1] == "add")
        ):
            start = 2
        elif len(argv) >= 2 and argv[0] == "npx":
            registry = _registry_from_argv(argv)
            package_options: list[str] = []
            index = 1
            while index < len(argv):
                value = argv[index]
                if value in {"-p", "--package"} and index + 1 < len(argv):
                    package_options.append(argv[index + 1])
                    index += 2
                    continue
                if value.startswith("--package="):
                    package_options.append(value.split("=", maxsplit=1)[1])
                index += 1
            if not package_options:
                package_options = [value for value in argv[1:] if not value.startswith("-")][:1]
            mentions.extend(
                _classify_spec(spec, requested_registry=registry) for spec in package_options
            )
            continue
        if start is None:
            continue
        registry = _registry_from_argv(argv)
        mentions.extend(
            _classify_spec(spec, requested_registry=registry)
            for index, spec in enumerate(argv[start:], start=start)
            if not spec.startswith("-")
            and not (index > start and argv[index - 1] == "--registry")
        )
    return mentions


def extract_npm_mentions(text: str) -> tuple[ExtractedPackage, ...]:
    """Extract npm registry intent without invoking a shell or package manager."""

    reject_shell_operators(text)
    manifest_mentions = _parse_manifest(text)
    pnpm_mentions = _parse_pnpm_lock(text)
    yarn_mentions = _parse_yarn_lock(text)
    if manifest_mentions or pnpm_mentions or yarn_mentions:
        return tuple(manifest_mentions + pnpm_mentions + yarn_mentions)
    return tuple(_parse_commands(text))
