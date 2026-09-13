from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_committed_report_includes_the_versioned_local_runtime_measurement() -> None:
    report = json.loads(
        (ROOT / "docs/measurements/holdout-v1.json").read_text(encoding="utf-8")
    )
    runtime_measurement = json.loads(
        (ROOT / "docs/measurements/guard-runtime-v1.json").read_text(encoding="utf-8")
    )

    assert report["dataset"]["examples"] == 200
    assert report["dataset"]["overlap_slots"] == 50
    assert report["dataset"]["teammate_2_labels_received"] == 0
    assert report["extraction"]["scope"] == "controlled deterministic seed corpus"
    assert report["extraction"]["precision"] == 1.0
    assert report["extraction"]["recall"] == 1.0
    assert report["demo_evidence"]["synthetic_replay"] is True
    assert report["runtime"] == runtime_measurement
    assert runtime_measurement["samples"] == 50
    assert runtime_measurement["protocol"] == (
        "HTTP loopback to the local Exasol-backed Guard API"
    )
    assert runtime_measurement["min_ms"] <= runtime_measurement["guard_p50_ms"]
    assert runtime_measurement["guard_p50_ms"] <= runtime_measurement["guard_p95_ms"]
    assert runtime_measurement["guard_p95_ms"] <= runtime_measurement["max_ms"]
    assert runtime_measurement["non_execution_invariant"] is True
