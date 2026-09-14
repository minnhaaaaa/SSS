"""Out-of-band operator intervention workflow."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

import httpx


@dataclass(frozen=True, slots=True)
class ApprovalRetry:
    token: str
    nonce: str
    request_id: str


class InterventionClient(Protocol):
    def list_pending(self) -> tuple[dict[str, object], ...]: ...

    def keep_blocked(self, intervention_id: str) -> None: ...

    def approve_once(self, intervention: dict[str, object]) -> ApprovalRetry: ...


class HttpInterventionClient:
    def __init__(self, *, api_url: str, token: str) -> None:
        self._api_url = api_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._client = httpx.Client(timeout=5, trust_env=False)

    def list_pending(self) -> tuple[dict[str, object], ...]:
        response = self._client.get(f"{self._api_url}/v1/interventions", headers=self._headers)
        response.raise_for_status()
        return tuple(response.json()["items"])

    def keep_blocked(self, intervention_id: str) -> None:
        response = self._client.post(
            f"{self._api_url}/v1/interventions/{intervention_id}/keep-blocked",
            headers={**self._headers, "Idempotency-Key": f"keep:{intervention_id}"},
        )
        response.raise_for_status()

    def approve_once(self, intervention: dict[str, object]) -> ApprovalRetry:
        intervention_id = str(intervention["intervention_id"])
        request = _mapping(intervention["request"])
        package = _mapping(request["package"])
        decision = _mapping(intervention["decision"])
        claims = {
            "package": package,
            "version": request["version_spec"],
            "registry_origin": package["registry_origin"],
            "artifact_sha256": request["artifact_sha256"],
            "project_id": request["project_id"],
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
            "nonce": str(uuid4()),
            "policy_version": decision["policy_version"],
        }
        response = self._client.post(
            f"{self._api_url}/v1/approvals",
            json={"intervention_id": intervention_id, "claims": claims},
            headers={**self._headers, "Idempotency-Key": f"approve:{intervention_id}"},
        )
        response.raise_for_status()
        payload = response.json()
        returned_claims = _mapping(payload["claims"])
        return ApprovalRetry(
            token=str(payload["token"]),
            nonce=str(returned_claims["nonce"]),
            request_id=str(request["request_id"]),
        )


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("intervention response is invalid")
    return value


def run_intervention(
    client: InterventionClient,
    *,
    input_line: Callable[[str], str],
    write: Callable[[str], None],
    once: bool,
) -> None:
    while True:
        pending = client.list_pending()
        if not pending:
            if once:
                return
            time.sleep(1)
            continue
        for intervention in pending:
            _handle_one(client, intervention, input_line=input_line, write=write)
            if once:
                return


def _handle_one(
    client: InterventionClient,
    intervention: dict[str, object],
    *,
    input_line: Callable[[str], str],
    write: Callable[[str], None],
) -> None:
    intervention_id = str(intervention["intervention_id"])
    request = _mapping(intervention["request"])
    package = _mapping(request["package"])
    decision = _mapping(intervention["decision"])
    scores = _mapping(decision["scores"])
    write("SSS operator intervention required")
    write(f"Package: {package['canonical_name']}@{request['version_spec']}")
    write(f"Registry: {package['registry_origin']}")
    write(
        "Scores: "
        f"absence {scores['absence_confidence']} / "
        f"attractiveness {scores['target_attractiveness']} / "
        f"risk {scores['package_policy_risk']}"
    )
    while True:
        try:
            answer = input_line(
                "[k]eep blocked (default), [i]nspect, [a]llow once: "
            ).strip().lower()
        except (EOFError, StopIteration):
            answer = ""
        if answer == "i":
            labels = intervention.get("evidence_labels", [])
            if isinstance(labels, list):
                for label in labels:
                    write(str(label))
            continue
        if answer == "a":
            retry = client.approve_once(intervention)
            write("Exact-scope approval issued for one use.")
            write(f"SSS_APPROVAL_TOKEN={retry.token}")
            write(f"SSS_APPROVAL_NONCE={retry.nonce}")
            write("Retry the same command with both values in its environment.")
            return
        client.keep_blocked(intervention_id)
        write("Installation remains blocked.")
        return
