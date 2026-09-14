from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from sss_core.domain import Ecosystem
from sss_core.extraction import PackageSource
from sss_core.extraction.python import extract_python_mentions


def test_extracts_pip_uv_and_pep508_requirements() -> None:
    text = """
pip install Django_REST.Framework==3.15 requests[socks]>=2
uv add rich~=13.0
"""

    mentions = extract_python_mentions(text)

    assert [(item.canonical_name, item.version_spec) for item in mentions] == [
        ("django-rest-framework", "==3.15"),
        ("requests", ">=2"),
        ("rich", "~=13.0"),
    ]
    assert all(item.ecosystem is Ecosystem.PYPI for item in mentions)


def test_extracts_pyproject_and_poetry_dependencies() -> None:
    text = """
[project]
dependencies = ["httpx>=0.28", "pydantic==2.10"]

[tool.poetry.dependencies]
python = "^3.12"
rich = "^13.9"
"""

    mentions = extract_python_mentions(text)

    assert [(item.canonical_name, item.version_spec) for item in mentions] == [
        ("httpx", ">=0.28"),
        ("pydantic", "==2.10"),
        ("rich", "^13.9"),
    ]


def test_poetry_table_and_group_dependencies_preserve_non_registry_sources() -> None:
    text = """
[tool.poetry.dependencies]
httpx = { version = "^0.28", extras = ["http2"] }
private-lib = { version = "1.0", source = "company" }
git-lib = { git = "https://github.com/example/git-lib.git", rev = "abc" }
local-lib = { path = "../local-lib" }

[tool.poetry.group.dev.dependencies]
pytest = "^8.3"
"""

    mentions = extract_python_mentions(text)

    assert [(item.canonical_name, item.version_spec, item.source) for item in mentions] == [
        ("httpx", "^0.28", PackageSource.REGISTRY),
        ("private-lib", "1.0", PackageSource.ALTERNATE_REGISTRY),
        ("git-lib", None, PackageSource.VCS),
        ("local-lib", None, PackageSource.LOCAL_PATH),
        ("pytest", "^8.3", PackageSource.REGISTRY),
    ]


def test_ast_imports_apply_aliases_and_exclude_standard_library() -> None:
    text = """
import json
import cv2
from sklearn.model_selection import train_test_split
"""

    mentions = extract_python_mentions(text)

    assert [item.canonical_name for item in mentions] == ["opencv-python", "scikit-learn"]
    assert all(item.source is PackageSource.IMPORT for item in mentions)


def test_direct_url_is_classified_without_fetching() -> None:
    mentions = extract_python_mentions(
        "pip install demo @ https://packages.example.invalid/demo-1.0.whl"
    )

    assert len(mentions) == 1
    assert mentions[0].canonical_name == "demo"
    assert mentions[0].source is PackageSource.DIRECT_URL


def test_extracts_requirements_file_and_classifies_non_registry_sources() -> None:
    text = """
requests[socks]==2.32
git+https://github.com/example/demo.git#egg=demo
./local-package
"""

    mentions = extract_python_mentions(text)

    assert [(item.canonical_name, item.source) for item in mentions] == [
        ("requests", PackageSource.REGISTRY),
        ("demo", PackageSource.VCS),
        ("./local-package", PackageSource.LOCAL_PATH),
    ]


def test_alternate_python_registry_is_preserved() -> None:
    mentions = extract_python_mentions(
        "pip install --index-url https://packages.example.invalid simple-package"
    )

    assert len(mentions) == 1
    assert mentions[0].source is PackageSource.ALTERNATE_REGISTRY
    assert mentions[0].requested_registry == "https://packages.example.invalid"


@given(st.from_regex(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,28}[A-Za-z0-9])?", fullmatch=True))
def test_canonical_python_names_survive_requirement_extraction(name: str) -> None:
    mentions = extract_python_mentions(f"pip install {name}")

    assert len(mentions) == 1
