from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from sss_core.domain import Ecosystem
from sss_core.extraction.npm import extract_npm_mentions
from sss_core.extraction.python import extract_python_mentions


@dataclass(frozen=True)
class ExtractionExample:
    expected: tuple[str, ...]
    actual: tuple[str, ...]


@dataclass(frozen=True)
class ExtractionMetrics:
    example_count: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def evaluate_extraction(examples: list[ExtractionExample]) -> ExtractionMetrics:
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    for example in examples:
        expected = Counter(example.expected)
        actual = Counter(example.actual)
        true_positives += sum((expected & actual).values())
        false_positives += sum((actual - expected).values())
        false_negatives += sum((expected - actual).values())
    return ExtractionMetrics(
        example_count=len(examples),
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=_ratio(true_positives, true_positives + false_positives),
        recall=_ratio(true_positives, true_positives + false_negatives),
    )


def evaluate_holdout(path: Path) -> ExtractionMetrics:
    examples: list[ExtractionExample] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = cast(dict[str, object], json.loads(line))
        ecosystem = Ecosystem(str(row["ecosystem"]))
        text = str(row["text"])
        label = cast(dict[str, object], row["teammate_1_label"])
        expected = tuple(str(name) for name in cast(list[object], label["canonical_names"]))
        mentions = (
            extract_python_mentions(text)
            if ecosystem is Ecosystem.PYPI
            else extract_npm_mentions(text)
        )
        examples.append(
            ExtractionExample(expected, tuple(mention.canonical_name for mention in mentions))
        )
    return evaluate_extraction(examples)


@dataclass(frozen=True)
class DemoMetrics:
    synthetic_replay: bool
    micro_hallucination_rate: float
    macro_hallucination_rate: float
    registry_unknown_rate: float
    public_signal_precision: float
    transition_delay_seconds: int
    guard_p50_ms: float | None = None
    guard_p95_ms: float | None = None
    non_execution_invariant: bool | None = None


def evaluate_demo_metrics(
    *,
    verified_runs_by_model: tuple[int, ...],
    observed_runs_by_model: tuple[int, ...],
    registry_checks: int,
    unknown_checks: int,
    validated_public_signals: int,
    observed_public_signals: int,
    registered_at: datetime,
    detected_at: datetime,
) -> DemoMetrics:
    if len(verified_runs_by_model) != len(observed_runs_by_model):
        raise ValueError("verified and observed model counts must align")
    model_rates = [
        _ratio(verified, observed)
        for verified, observed in zip(
            verified_runs_by_model, observed_runs_by_model, strict=True
        )
    ]
    return DemoMetrics(
        synthetic_replay=True,
        micro_hallucination_rate=_ratio(
            sum(verified_runs_by_model), sum(observed_runs_by_model)
        ),
        macro_hallucination_rate=(sum(model_rates) / len(model_rates) if model_rates else 0.0),
        registry_unknown_rate=_ratio(unknown_checks, registry_checks),
        public_signal_precision=_ratio(validated_public_signals, observed_public_signals),
        transition_delay_seconds=int((detected_at - registered_at).total_seconds()),
    )
