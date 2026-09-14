from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sss_core.measurement import (
    ExtractionExample,
    evaluate_demo_metrics,
    evaluate_extraction,
)


def test_extraction_metrics_count_false_positives_and_false_negatives() -> None:
    metrics = evaluate_extraction(
        [
            ExtractionExample(("requests",), ("requests",)),
            ExtractionExample(("httpx",), ("wrong",)),
            ExtractionExample((), ("extra",)),
        ]
    )

    assert metrics.true_positives == 1
    assert metrics.false_positives == 2
    assert metrics.false_negatives == 1
    assert metrics.precision == 1 / 3
    assert metrics.recall == 1 / 2


def test_demo_metrics_are_explicitly_synthetic_and_keep_runtime_fields_unmeasured() -> None:
    registered = datetime(2026, 9, 12, 12, tzinfo=UTC)
    metrics = evaluate_demo_metrics(
        verified_runs_by_model=(16, 15, 15),
        observed_runs_by_model=(16, 15, 15),
        registry_checks=1,
        unknown_checks=0,
        validated_public_signals=5,
        observed_public_signals=5,
        registered_at=registered,
        detected_at=registered + timedelta(minutes=43),
    )

    assert metrics.synthetic_replay is True
    assert metrics.micro_hallucination_rate == 1.0
    assert metrics.macro_hallucination_rate == 1.0
    assert metrics.registry_unknown_rate == 0.0
    assert metrics.public_signal_precision == 1.0
    assert metrics.transition_delay_seconds == 2580
    assert metrics.guard_p50_ms is None
    assert metrics.guard_p95_ms is None
    assert metrics.non_execution_invariant is None
