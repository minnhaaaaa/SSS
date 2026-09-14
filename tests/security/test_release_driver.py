from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_browser_smoke_waits_for_reveal_motion_before_screenshot() -> None:
    driver = (ROOT / "scripts/validate_production.sh").read_text(encoding="utf-8")

    assert driver.count("--virtual-time-budget=3000") == 2
