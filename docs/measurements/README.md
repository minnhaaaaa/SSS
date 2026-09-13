# Measurement status

`mentions-v1.jsonl` is a deterministic 200-example parser seed corpus: 100 PyPI and 100 npm
examples spanning the supported command clients. Its perfect extraction result is a controlled
regression result, **not a real-world accuracy claim**.

Teammate 1 has labelled all 200 rows. Exactly 50 rows (25 per ecosystem) are marked for independent
overlap review. Their `teammate_2_label` remains null until Teammate 2's actual labels are imported;
the dataset must be re-hashed and disagreements documented after that merge. Null is deliberate and
must never be presented as agreement.

The demo evidence rates are also labelled synthetic replay. They prove metric calculation and fixed
fixture consistency, not a population estimate. Guard p50/p95 and the non-execution invariant remain
null until Teammate 2's integrated protected-workspace run supplies real measurements.

Regenerate and validate:

```bash
uv run python scripts/generate_holdout.py
uv run python scripts/measure_holdout.py
uv run python scripts/generate_holdout.py --check
uv run python scripts/measure_holdout.py --check
```
