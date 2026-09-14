from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_recording_script_uses_only_controlled_demo_targets_and_masks_grants() -> None:
    script = (ROOT / "scripts/record_demo.sh").read_text(encoding="utf-8")

    assert "https://registry.npmjs.org" not in script
    assert "SSS_APPROVAL_TOKEN=[hidden]" not in script
    assert "SSS_APPROVAL_(TOKEN|NONCE)" in script
    assert "https://npm.demo.sss.test" not in script
    assert "SSS_CANARY_TOKEN=demo-canary-token" in script
    assert "compose down -v --remove-orphans" in script
    assert "test \"$replay_code\" -eq 23" in script
