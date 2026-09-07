from __future__ import annotations

import ast
import json
import shlex
import sys
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from sss_core.domain import Ecosystem
from sss_core.extraction import ExtractedPackage, PackageSource
from sss_core.extraction._safety import reject_shell_operators

_ROOT = Path(__file__).parents[4]
_ALIASES_PATH = _ROOT / "data/import_aliases.json"
_STDLIB_PATH = _ROOT / "data/stdlib_manifest.json"


def _load_aliases() -> dict[str, str]:
    document = json.loads(_ALIASES_PATH.read_text(encoding="utf-8"))
    aliases = document["aliases"]
    if not isinstance(aliases, dict):
        raise ValueError("alias table must contain an aliases object")
    return {str(key): str(value) for key, value in aliases.items()}


def _load_stdlib() -> frozenset[str]:
    document = json.loads(_STDLIB_PATH.read_text(encoding="utf-8"))
    modules = document["modules"]
    if not isinstance(modules, list):
        raise ValueError("stdlib manifest must contain a modules array")
    return frozenset(str(module) for module in modules) | frozenset(sys.stdlib_module_names)


def _from_requirement(
    raw: str,
    *,
    source: PackageSource = PackageSource.REGISTRY,
    requested_registry: str | None = None,
) -> ExtractedPackage:
    requirement = Requirement(raw)
    package_source = PackageSource.DIRECT_URL if requirement.url else source
    return ExtractedPackage(
        ecosystem=Ecosystem.PYPI,
        raw=raw,
        canonical_name=str(canonicalize_name(requirement.name)),
        version_spec=str(requirement.specifier) or None,
        source=package_source,
        requested_registry=requested_registry,
    )


def _parse_toml(text: str) -> list[ExtractedPackage]:
    if "[project]" not in text and "[tool.poetry.dependencies]" not in text:
        return []
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []

    mentions: list[ExtractedPackage] = []
    project = document.get("project", {})
    if isinstance(project, dict):
        dependencies = project.get("dependencies", [])
        if isinstance(dependencies, list):
            for dependency in dependencies:
                if isinstance(dependency, str):
                    mentions.append(_from_requirement(dependency))

    tool = document.get("tool", {})
    poetry: Any = tool.get("poetry", {}) if isinstance(tool, dict) else {}
    dependencies = poetry.get("dependencies", {}) if isinstance(poetry, dict) else {}
    if isinstance(dependencies, dict):
        for name, value in dependencies.items():
            if name == "python" or not isinstance(value, str):
                continue
            mentions.append(
                ExtractedPackage(
                    ecosystem=Ecosystem.PYPI,
                    raw=f"{name}{value}",
                    canonical_name=str(canonicalize_name(name)),
                    version_spec=value,
                    source=PackageSource.REGISTRY,
                )
            )
    return mentions


def _command_requirements(line: str) -> list[str]:
    try:
        argv = shlex.split(line)
    except ValueError:
        return []
    start: int | None = None
    if len(argv) >= 2 and argv[0] in {"pip", "pip3"} and argv[1] == "install":
        start = 2
    elif len(argv) >= 4 and argv[:3] == ["python", "-m", "pip"] and argv[3] == "install":
        start = 4
    elif len(argv) >= 2 and argv[0] == "uv" and argv[1] == "add":
        start = 2
    elif len(argv) >= 3 and argv[:3] == ["uv", "pip", "install"]:
        start = 3
    if start is None:
        return []

    values = [value for value in argv[start:] if not value.startswith("-")]
    requirements: list[str] = []
    index = 0
    while index < len(values):
        if index + 2 < len(values) and values[index + 1] == "@":
            requirements.append(" ".join(values[index : index + 3]))
            index += 3
        else:
            requirements.append(values[index])
            index += 1
    return requirements


def _registry_from_argv(argv: list[str]) -> str | None:
    for index, value in enumerate(argv):
        if value in {"--index-url", "--extra-index-url"} and index + 1 < len(argv):
            candidate = argv[index + 1]
        elif value.startswith(("--index-url=", "--extra-index-url=")):
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
        registry = _registry_from_argv(argv)
        for raw in _command_requirements(line.strip()):
            if raw.startswith("https://") and registry == raw.rstrip("/"):
                continue
            try:
                mentions.append(
                    _from_requirement(
                        raw,
                        source=(
                            PackageSource.ALTERNATE_REGISTRY
                            if registry is not None
                            else PackageSource.REGISTRY
                        ),
                        requested_registry=registry,
                    )
                )
            except InvalidRequirement:
                continue
    return mentions


def _parse_requirements_text(text: str) -> list[ExtractedPackage]:
    mentions: list[ExtractedPackage] = []
    for line in text.splitlines():
        raw = line.strip()
        if (
            not raw
            or raw.startswith(("#", "[", "import ", "from "))
            or _command_requirements(raw)
            or " = " in raw
        ):
            continue
        if raw.startswith(("./", "../", "/")):
            mentions.append(
                ExtractedPackage(Ecosystem.PYPI, raw, raw, None, PackageSource.LOCAL_PATH)
            )
            continue
        if raw.startswith(("git+", "git://")):
            egg = raw.partition("#egg=")[2]
            mentions.append(
                ExtractedPackage(
                    Ecosystem.PYPI,
                    raw,
                    str(canonicalize_name(egg)) if egg else raw,
                    None,
                    PackageSource.VCS,
                )
            )
            continue
        try:
            mentions.append(_from_requirement(raw))
        except InvalidRequirement:
            continue
    return mentions


def _parse_imports(text: str) -> list[ExtractedPackage]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    aliases = _load_aliases()
    stdlib = _load_stdlib()
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module.split(".", maxsplit=1)[0])

    mentions: list[ExtractedPackage] = []
    for name in names:
        if name in stdlib:
            continue
        distribution = aliases.get(name)
        if distribution is None:
            continue
        mentions.append(
            ExtractedPackage(
                ecosystem=Ecosystem.PYPI,
                raw=name,
                canonical_name=str(canonicalize_name(distribution)),
                version_spec=None,
                source=PackageSource.IMPORT,
            )
        )
    return mentions


def extract_python_mentions(text: str) -> tuple[ExtractedPackage, ...]:
    """Extract Python distribution intent without evaluating shell or source text."""

    reject_shell_operators(text)
    toml_mentions = _parse_toml(text)
    command_mentions = _parse_commands(text)
    requirements_mentions = [] if toml_mentions else _parse_requirements_text(text)
    return tuple(toml_mentions + command_mentions + requirements_mentions + _parse_imports(text))
