from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from sss_core.domain import Ecosystem, EvidenceProvenance
from sss_worker.jobs.probe import (
    MemoryObservationSink,
    PromptTask,
    load_prompt_manifest,
    run_probe_suite,
)
from sss_worker.providers.replay import ReplayProvider

ROOT = Path(__file__).parents[2]


def test_prompt_manifest_contains_48_hashed_cross_ecosystem_tasks() -> None:
    tasks = load_prompt_manifest(ROOT / "demo/fixtures/probe_corpus.jsonl")

    assert len(tasks) == 48
    assert {task.ecosystem for task in tasks} == {Ecosystem.PYPI, Ecosystem.NPM}
    assert len({task.category for task in tasks}) >= 6
    expected_hashes = {hashlib.sha256(task.prompt.encode()).hexdigest() for task in tasks}
    assert {task.prompt_sha256 for task in tasks} == expected_hashes


@pytest.mark.asyncio
async def test_duplicate_replay_does_not_duplicate_mentions_or_recurrence() -> None:
    task = PromptTask.create("task-1", "web", Ecosystem.PYPI, "Build a web API")
    provider = ReplayProvider(
        provider="fixture",
        model_id="replay-v1",
        parameters={"temperature": 0},
        responses={"task-1": "pip install imaginary-web-helper"},
    )
    sink = MemoryObservationSink()

    first = await run_probe_suite(provider, [task], sink)
    second = await run_probe_suite(provider, [task], sink)

    assert first.new_mentions == 1
    assert second.new_mentions == 0
    assert sink.mention_count == 1
    assert sink.recurrence_count("pypi", "imaginary-web-helper") == 1
    observation = next(iter(sink.observations.values()))
    assert observation.provenance is EvidenceProvenance.MODEL_PROBE
    assert observation.model_configuration_sha256


def test_probe_fixture_lines_are_valid_json() -> None:
    path = ROOT / "demo/fixtures/probe_corpus.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        assert isinstance(json.loads(line), dict)
