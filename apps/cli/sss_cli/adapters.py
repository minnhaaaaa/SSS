"""HTTP adapter for the authenticated Guard API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from sss_core import Decision, EvidenceScores, InstallRequest


class GuardAdapterError(RuntimeError):
    """Raised when an assessment cannot be obtained or validated."""


@dataclass(frozen=True, slots=True)
class GuardDecisionResult:
    decision_id: str
    decision: Decision
    reason_codes: tuple[str, ...]
    scores: EvidenceScores
    policy_version: str
    intervention_id: str | None
    child_process_allowed: bool


class HttpGuardClient:
    def __init__(
        self,
        *,
        api_url: str,
        token: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._token = token
        self._client = http_client or httpx.Client(timeout=5, trust_env=False)

    @property
    def _authorization(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def check(self, request: InstallRequest) -> GuardDecisionResult:
        try:
            response = self._client.post(
                f"{self._api_url}/v1/check",
                json=_request_payload(request),
                headers={**self._authorization, "Idempotency-Key": request.request_id},
            )
            response.raise_for_status()
            payload = response.json()
            scores = payload["scores"]
            return GuardDecisionResult(
                decision_id=str(payload["decision_id"]),
                decision=Decision(str(payload["decision"])),
                reason_codes=tuple(str(code) for code in payload["reason_codes"]),
                scores=EvidenceScores(
                    absence_confidence=_optional_int(scores["absence_confidence"]),
                    target_attractiveness=int(scores["target_attractiveness"]),
                    package_policy_risk=int(scores["package_policy_risk"]),
                ),
                policy_version=str(payload["policy_version"]),
                intervention_id=(
                    str(payload["intervention_id"])
                    if payload.get("intervention_id") is not None
                    else None
                ),
                child_process_allowed=payload["child_process_allowed"] is True,
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise GuardAdapterError("Guard assessment unavailable") from exc

    def record_attempt(self, **payload: object) -> None:
        try:
            response = self._client.post(
                f"{self._api_url}/v1/install-attempts",
                json=payload,
                headers={
                    **self._authorization,
                    "Idempotency-Key": f"attempt:{payload['decision_id']}",
                },
            )
            response.raise_for_status()
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise GuardAdapterError("install attempt could not be recorded") from exc


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _request_payload(request: InstallRequest) -> dict[str, object]:
    return {
        "request_id": request.request_id,
        "project_id": request.project_id,
        "agent_family": request.agent_family,
        "package": {
            "ecosystem": request.package.ecosystem.value,
            "registry_origin": request.package.registry_origin,
            "canonical_name": request.package.canonical_name,
        },
        "version_spec": request.version_spec,
        "direct_url": request.direct_url,
        "artifact_sha256": request.artifact_sha256,
        "is_direct": request.is_direct,
    }
