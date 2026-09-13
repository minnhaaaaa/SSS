from __future__ import annotations

import json
import subprocess
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st
from sss_core.extraction import PackageSource
from sss_core.extraction.npm import extract_npm_mentions

ROOT = Path(__file__).parents[2]


def test_extracts_npm_pnpm_yarn_and_npx_specs() -> None:
    text = """
npm install react@19 @Scope/Thing@^2
pnpm add zod@^3
yarn add lodash@4
npx vite@latest
"""

    mentions = extract_npm_mentions(text)

    assert [(item.canonical_name, item.version_spec) for item in mentions] == [
        ("react", "19"),
        ("@scope/thing", "^2"),
        ("zod", "^3"),
        ("lodash", "4"),
        ("vite", "latest"),
    ]


def test_npx_package_option_extracts_the_package_not_the_executed_binary() -> None:
    mentions = extract_npm_mentions("npx --yes --package typescript@5 tsc --version")

    assert [(item.canonical_name, item.version_spec) for item in mentions] == [
        ("typescript", "5")
    ]


def test_extracts_direct_package_json_dependencies() -> None:
    text = json.dumps(
        {
            "dependencies": {"react": "^19", "@Scope/Thing": "1.2.3"},
            "devDependencies": {"vitest": "latest"},
        }
    )

    mentions = extract_npm_mentions(text)

    assert [(item.canonical_name, item.version_spec) for item in mentions] == [
        ("@scope/thing", "1.2.3"),
        ("react", "^19"),
        ("vitest", "latest"),
    ]
    assert all(item.is_direct for item in mentions)


def test_extracts_package_lock_root_dependencies_only() -> None:
    text = json.dumps(
        {
            "lockfileVersion": 3,
            "packages": {
                "": {"dependencies": {"react": "^19"}},
                "node_modules/react": {"version": "19.0.0"},
            },
        }
    )

    mentions = extract_npm_mentions(text)

    assert [(item.canonical_name, item.version_spec) for item in mentions] == [("react", "^19")]


def test_extracts_pnpm_and_yarn_lock_direct_entries() -> None:
    pnpm_lock = """
lockfileVersion: '9.0'
importers:
  .:
    dependencies:
      react:
        specifier: ^19
        version: 19.0.0
"""
    yarn_lock = 'react@^19:\n  version "19.0.0"\n'

    pnpm_mentions = extract_npm_mentions(pnpm_lock)
    yarn_mentions = extract_npm_mentions(yarn_lock)

    assert [(item.canonical_name, item.version_spec) for item in pnpm_mentions] == [
        ("react", "^19")
    ]
    assert [(item.canonical_name, item.version_spec) for item in yarn_mentions] == [
        ("react", "^19")
    ]


def test_alias_git_url_and_path_specs_are_classified() -> None:
    mentions = extract_npm_mentions(
        "npm install alias@npm:real-package@1 git+https://github.com/org/repo.git ./local"
    )

    assert [item.source for item in mentions] == [
        PackageSource.ALIAS,
        PackageSource.VCS,
        PackageSource.LOCAL_PATH,
    ]


def test_alternate_npm_registry_is_preserved() -> None:
    mentions = extract_npm_mentions(
        "npm install --registry=https://packages.example.invalid package-name"
    )

    assert len(mentions) == 1
    assert mentions[0].source is PackageSource.ALTERNATE_REGISTRY
    assert mentions[0].requested_registry == "https://packages.example.invalid"


def test_node_helper_returns_classification_and_never_install_instructions() -> None:
    process = subprocess.run(
        ["node", "index.mjs"],
        cwd=ROOT / "helpers/npm-spec-parser",
        input='{"spec":"@scope/name@^2"}\n',
        text=True,
        capture_output=True,
        check=True,
    )

    result = json.loads(process.stdout)
    assert result == {
        "name": "@scope/name",
        "rawSpec": "^2",
        "type": "range",
        "fetchSpec": "^2",
    }


@given(st.from_regex(r"[a-z][a-z0-9-]{0,30}", fullmatch=True))
def test_canonical_npm_names_survive_extraction(name: str) -> None:
    mentions = extract_npm_mentions(f"pnpm add {name}")

    assert mentions[0].canonical_name == name
