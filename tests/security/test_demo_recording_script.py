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


def test_rendered_demo_types_commands_before_revealing_output() -> None:
    page = (ROOT / "docs/demo-video/terminal-demo.html").read_text(encoding="utf-8")
    renderer = (ROOT / "scripts/render_demo_video.sh").read_text(encoding="utf-8")

    assert "terminal-type" in page
    assert "steps(var(--command-length), end)" in page
    assert "terminal-output-reveal" in page
    assert "clip-path: inset(0 100% 0 0)" in page
    assert "terminal-cursor-arrive" in page
    assert "translateX(var(--command-width))" in page
    assert "width: calc(var(--command-length) * 1ch)" not in page
    assert "prefers-reduced-motion: reduce" in page
    assert "--virtual-time-budget" in renderer
