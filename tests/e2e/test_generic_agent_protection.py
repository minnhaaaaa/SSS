from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
SHIMS = ROOT / "apps/cli/sss_cli/shims"


@pytest.mark.parametrize(
    "name", ["pip", "pip3", "python", "uv", "poetry", "npm", "pnpm", "yarn", "npx"]
)
def test_every_installed_shim_is_executable_and_uses_common_dispatch(name: str) -> None:
    shim = SHIMS / name
    assert shim.is_file()
    assert shim.stat().st_mode & 0o111
    text = shim.read_text(encoding="utf-8")
    assert "main_for_executable" in text
    assert "subprocess" not in text
    compile(text, str(shim), "exec")
