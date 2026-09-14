from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sss_core.measurement import evaluate_holdout

from scripts.generate_holdout import render_holdout

ROOT = Path(__file__).parents[2]
DATASET = ROOT / "data/holdout/mentions-v1.jsonl"


def test_holdout_is_reproducible_cross_ecosystem_and_has_fifty_overlap_slots() -> None:
    committed = DATASET.read_bytes()
    rows = [json.loads(line) for line in committed.decode().splitlines()]

    assert committed == render_holdout()
    assert len(rows) == 200
    assert sum(row["ecosystem"] == "pypi" for row in rows) == 100
    assert sum(row["ecosystem"] == "npm" for row in rows) == 100
    assert sum(row["overlap"] for row in rows) == 50
    assert all(row["teammate_1_label"] is not None for row in rows)
    assert all(row["teammate_2_label"] is None for row in rows)


def test_holdout_hash_and_controlled_extraction_measurement_are_stable() -> None:
    digest = hashlib.sha256(DATASET.read_bytes()).hexdigest()
    expected_digest = (ROOT / "data/holdout/mentions-v1.sha256").read_text().strip()
    metrics = evaluate_holdout(DATASET)

    assert digest == expected_digest
    assert metrics.example_count == 200
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
