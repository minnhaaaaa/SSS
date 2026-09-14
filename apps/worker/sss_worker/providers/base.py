from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderResponse:
    provider: str
    model_id: str
    parameters: dict[str, object]
    text: str


class ModelProvider(Protocol):
    async def generate(self, task_id: str, prompt: str) -> ProviderResponse: ...
