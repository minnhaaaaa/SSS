from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from sss_core.demo import load_demo_fixture
from sss_core.measurement import evaluate_demo_metrics, evaluate_holdout

ROOT = Path(__file__).parents[1]
DATASET = ROOT / "data/holdout/mentions-v1.jsonl"
REPORT = ROOT / "docs/measurements/holdout-v1.json"


def build_report() -> dict[str, object]:
    rows = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines()]
    extraction = evaluate_holdout(DATASET)
    fixture = load_demo_fixture(ROOT / "demo/fixtures/fixed-intelligence.json")
    demo = evaluate_demo_metrics(
        verified_runs_by_model=(16, 15, 15),
        observed_runs_by_model=(16, 15, 15),
        registry_checks=1,
        unknown_checks=0,
        validated_public_signals=5,
        observed_public_signals=5,
        registered_at=fixture.registered_at,
        detected_at=fixture.attack_at,
    )
    extraction_values = asdict(extraction)
    extraction_values["scope"] = "controlled deterministic seed corpus"
    demo_values = asdict(demo)
    runtime = {
        "guard_p50_ms": demo_values.pop("guard_p50_ms"),
        "guard_p95_ms": demo_values.pop("guard_p95_ms"),
        "non_execution_invariant": demo_values.pop("non_execution_invariant"),
        "owner": "Teammate 2 integration/E2E",
    }
    return {
        "dataset": {
            "path": "data/holdout/mentions-v1.jsonl",
            "sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
            "examples": len(rows),
            "pypi_examples": sum(row["ecosystem"] == "pypi" for row in rows),
            "npm_examples": sum(row["ecosystem"] == "npm" for row in rows),
            "overlap_slots": sum(bool(row["overlap"]) for row in rows),
            "teammate_1_labels": sum(row["teammate_1_label"] is not None for row in rows),
            "teammate_2_labels_received": sum(
                row["teammate_2_label"] is not None for row in rows
            ),
            "reconciliation_status": "pending Teammate 2 label import",
        },
        "extraction": extraction_values,
        "demo_evidence": demo_values,
        "runtime": runtime,
    }


def render_report() -> bytes:
    return (json.dumps(build_report(), indent=2, sort_keys=True) + "\n").encode()


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure the frozen SSS seed corpus")
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    content = render_report()
    if arguments.check:
        if not REPORT.exists() or REPORT.read_bytes() != content:
            raise SystemExit("measurement report is stale; regenerate it")
        return
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_bytes(content)


if __name__ == "__main__":
    main()
