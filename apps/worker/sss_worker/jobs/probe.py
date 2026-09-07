from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from sss_core.domain import Ecosystem, EvidenceProvenance
from sss_core.extraction.npm import extract_npm_mentions
from sss_core.extraction.python import extract_python_mentions

from sss_worker.providers.base import ModelProvider


@dataclass(frozen=True)
class PromptTask:
    task_id: str
    category: str
    ecosystem: Ecosystem
    prompt: str
    prompt_sha256: str

    @classmethod
    def create(
        cls,
        task_id: str,
        category: str,
        ecosystem: Ecosystem,
        prompt: str,
    ) -> PromptTask:
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        return cls(task_id, category, ecosystem, prompt, prompt_hash)


@dataclass(frozen=True)
class CollectedObservation:
    observation_id: str
    ecosystem: Ecosystem
    canonical_name: str
    provenance: EvidenceProvenance
    source_id: str
    model_configuration_sha256: str | None


@dataclass(frozen=True)
class CollectionResult:
    new_mentions: int
    rate_limited: bool = False


class MemoryObservationSink:
    def __init__(self) -> None:
        self.observations: dict[str, CollectedObservation] = {}
        self._cursors: dict[str, str | None] = {}
        self.deletions: set[str] = set()

    @property
    def mention_count(self) -> int:
        return len(self.observations)

    def record(self, observation: CollectedObservation) -> bool:
        if observation.observation_id in self.observations:
            return False
        self.observations[observation.observation_id] = observation
        return True

    def recurrence_count(self, ecosystem: str, canonical_name: str) -> int:
        return len(
            {
                item.source_id
                for item in self.observations.values()
                if item.ecosystem.value == ecosystem and item.canonical_name == canonical_name
            }
        )

    def save_cursor(self, source: str, cursor: str | None) -> None:
        self._cursors[source] = cursor

    def cursor(self, source: str) -> str | None:
        return self._cursors.get(source)

    def record_deletion(self, source_id: str) -> None:
        self.deletions.add(source_id)


def load_prompt_manifest(path: Path) -> tuple[PromptTask, ...]:
    tasks: list[PromptTask] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        tasks.append(
            PromptTask.create(
                str(value["task_id"]),
                str(value["category"]),
                Ecosystem(str(value["ecosystem"])),
                str(value["prompt"]),
            )
        )
    return tuple(tasks)


def _observation_id(
    provenance: EvidenceProvenance,
    source_id: str,
    ecosystem: Ecosystem,
    canonical_name: str,
) -> str:
    key = "\0".join((provenance.value, source_id, ecosystem.value, canonical_name))
    return hashlib.sha256(key.encode()).hexdigest()


def make_observation(
    *,
    provenance: EvidenceProvenance,
    source_id: str,
    ecosystem: Ecosystem,
    canonical_name: str,
    model_configuration_sha256: str | None = None,
) -> CollectedObservation:
    return CollectedObservation(
        _observation_id(provenance, source_id, ecosystem, canonical_name),
        ecosystem,
        canonical_name,
        provenance,
        source_id,
        model_configuration_sha256,
    )


async def run_probe_suite(
    provider: ModelProvider,
    tasks: list[PromptTask],
    sink: MemoryObservationSink,
) -> CollectionResult:
    new_mentions = 0
    for task in tasks:
        response = await provider.generate(task.task_id, task.prompt)
        configuration = json.dumps(
            {
                "provider": response.provider,
                "model_id": response.model_id,
                "parameters": response.parameters,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        configuration_hash = hashlib.sha256(configuration.encode()).hexdigest()
        response_hash = hashlib.sha256(response.text.encode()).hexdigest()
        run_id = hashlib.sha256(
            f"{configuration_hash}:{task.prompt_sha256}:{response_hash}".encode()
        ).hexdigest()
        mentions = (
            extract_python_mentions(response.text)
            if task.ecosystem is Ecosystem.PYPI
            else extract_npm_mentions(response.text)
        )
        for mention in mentions:
            observation = make_observation(
                provenance=EvidenceProvenance.MODEL_PROBE,
                source_id=run_id,
                ecosystem=task.ecosystem,
                canonical_name=mention.canonical_name,
                model_configuration_sha256=configuration_hash,
            )
            new_mentions += sink.record(observation)
    return CollectionResult(new_mentions)
