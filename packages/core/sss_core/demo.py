from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

from sss_core.domain import Ecosystem, EvidenceScores, PackageIdentity


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an RFC 3339 timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


@dataclass(frozen=True)
class FixedDemoFixture:
    fixture_version: str
    package: PackageIdentity
    registration_origin: str
    verified_model_recommendations: int
    model_configurations: int
    protected_agent_attempts: int
    observation_days: int
    public_failed_references: int
    first_absence_at: datetime
    registered_at: datetime
    attack_at: datetime
    scores: EvidenceScores
    policy_version: str
    evidence_label: str

    def __post_init__(self) -> None:
        if self.registration_origin != self.package.registry_origin:
            raise ValueError("absence and registration must use the same registry origin")
        if self.registered_at - self.first_absence_at != timedelta(days=11):
            raise ValueError("fixed demo registration must be eleven days after first absence")
        if self.attack_at - self.registered_at != timedelta(minutes=43):
            raise ValueError("fixed demo attack must be 43 minutes after registration")
        if (
            self.verified_model_recommendations,
            self.model_configurations,
            self.protected_agent_attempts,
            self.observation_days,
            self.public_failed_references,
        ) != (46, 3, 8, 11, 5):
            raise ValueError("fixed demo recurrence values must remain 46/3/8/11/5")
        if self.scores != EvidenceScores(100, 95, 75):
            raise ValueError("fixed demo scores must remain 100/95/75")
        if self.policy_version != "sss-hackathon-v3":
            raise ValueError("fixed demo policy version is not active")

    @property
    def registration_age_minutes(self) -> int:
        return int((self.attack_at - self.registered_at).total_seconds() // 60)

    def mention_rows(self) -> tuple[dict[str, Any], ...]:
        rows: list[dict[str, Any]] = []
        first_observation_day = self.registered_at - timedelta(days=self.observation_days - 1)
        for index in range(self.verified_model_recommendations):
            rows.append(
                {
                    "mention_id": f"demo-model-mention-{index:03d}",
                    "provenance": "model_probe",
                    "source_id": f"demo-run-{index:03d}",
                    "model_configuration_id": f"demo-model-{index % self.model_configurations}",
                    "observed_at": first_observation_day
                    + timedelta(days=index % self.observation_days),
                    "context_kind": "explicit_install",
                }
            )
        for index in range(self.protected_agent_attempts):
            rows.append(
                {
                    "mention_id": f"demo-client-mention-{index:03d}",
                    "provenance": "agent_install_attempt",
                    "source_id": f"demo-client-{index:02d}",
                    "model_configuration_id": None,
                    "observed_at": self.attack_at,
                    "context_kind": "registry",
                }
            )
        for index in range(self.public_failed_references):
            rows.append(
                {
                    "mention_id": f"demo-public-mention-{index:03d}",
                    "provenance": "public_ci_failure",
                    "source_id": f"demo-public-{index:02d}",
                    "model_configuration_id": None,
                    "observed_at": first_observation_day + timedelta(days=index),
                    "context_kind": "explicit_install",
                }
            )
        return tuple(rows)


def load_demo_fixture(path: Path) -> FixedDemoFixture:
    document = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    package = cast(dict[str, object], document["package"])
    if document.get("registration_origin") != package.get("registry_origin"):
        raise ValueError("absence and registration must use the same registry origin")
    scores = cast(dict[str, object], document["scores"])
    return FixedDemoFixture(
        fixture_version=str(document["fixture_version"]),
        package=PackageIdentity(
            ecosystem=Ecosystem(str(package["ecosystem"])),
            registry_origin=str(package["registry_origin"]),
            canonical_name=str(package["canonical_name"]),
        ),
        registration_origin=str(document["registration_origin"]),
        verified_model_recommendations=int(cast(int, document["verified_model_recommendations"])),
        model_configurations=int(cast(int, document["model_configurations"])),
        protected_agent_attempts=int(cast(int, document["protected_agent_attempts"])),
        observation_days=int(cast(int, document["observation_days"])),
        public_failed_references=int(cast(int, document["public_failed_references"])),
        first_absence_at=_timestamp(document["first_absence_at"], "first_absence_at"),
        registered_at=_timestamp(document["registered_at"], "registered_at"),
        attack_at=_timestamp(document["attack_at"], "attack_at"),
        scores=EvidenceScores(
            absence_confidence=int(cast(int, scores["absence_confidence"])),
            target_attractiveness=int(cast(int, scores["target_attractiveness"])),
            package_policy_risk=int(cast(int, scores["package_policy_risk"])),
        ),
        policy_version=str(document["policy_version"]),
        evidence_label=str(document["evidence_label"]),
    )
