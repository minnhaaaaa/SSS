from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_committed_report_does_not_claim_unmeasured_runtime_results() -> None:
    report = json.loads(
        (ROOT / "docs/measurements/holdout-v1.json").read_text(encoding="utf-8")
    )

    assert report["dataset"]["examples"] == 200
    assert report["dataset"]["overlap_slots"] == 50
    assert report["dataset"]["teammate_2_labels_received"] == 0
    assert report["extraction"]["scope"] == "controlled deterministic seed corpus"
    assert report["extraction"]["precision"] == 1.0
    assert report["extraction"]["recall"] == 1.0
    assert report["demo_evidence"]["synthetic_replay"] is True
    assert report["runtime"]["guard_p50_ms"] is None
    assert report["runtime"]["guard_p95_ms"] is None
    assert report["runtime"]["non_execution_invariant"] is None
