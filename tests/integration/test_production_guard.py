from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import httpx
import pytest
from sss_api.config import ApiSettings
from sss_api.events import EventBroker
from sss_api.main import create_app
from sss_api.services.guard import ExasolEvidenceProvider, GuardService
from sss_api.services.interventions import InterventionStore
from sss_core import POLICY_VERSION, Ecosystem, InstallRequest, PackageIdentity, PolicyEngine
from sss_core.domain import CandidateStatus
from sss_core.evidence.facts import EvidenceFacts
from sss_core.registries.base import RegistryOutcome


@pytest.mark.asyncio
async def test_production_guard_scores_an_arbitrary_transition() -> None:
    identity = PackageIdentity(
        Ecosystem.NPM, "https://registry.npmjs.org", "novel-agent-tool"
    )
    facts = EvidenceFacts(
        CandidateStatus.REGISTERED_AFTER_ABSENCE,
        RegistryOutcome.REGISTERED,
        True,
        True,
        20,
        2,
        6,
        4,
        3,
        True,
        12.0,
        False,
        False,
        datetime.now(UTC),
    )

    class Repository:
        def load_facts(self, package: PackageIdentity) -> EvidenceFacts:
            assert package == identity
            return facts

    broker = EventBroker(capacity=10)
    service = GuardService(
        PolicyEngine(), ExasolEvidenceProvider(Repository()), InterventionStore(), broker
    )
    assessment = await service.check(
        InstallRequest("request-1", "project-1", "codex", identity, "1.0.0", None, None, True)
    )

    assert assessment.decision.decision.value == "block"
    assert assessment.decision.scores.target_attractiveness == 62
    assert assessment.decision.scores.package_policy_risk == 75
    assert "REGISTERED_AFTER_HALLUCINATION" in assessment.decision.reason_codes


@pytest.mark.skipif(
    not os.getenv("SSS_EXASOL_DSN"), reason="requires an explicitly provisioned Exasol database"
)
@pytest.mark.asyncio
async def test_live_production_ingestion_guard_and_radar(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    suffix = uuid4().hex
    name = f"novel-agent-tool-{suffix}"
    collector = f"collector-{suffix}"
    agent = f"agent-{suffix}"
    radar = f"radar-{suffix}"
    credentials = tmp_path / "credentials.json"
    credentials.write_text(
        json.dumps(
            {
                "credentials": [
                    {
                        "credential_id": collector,
                        "token_sha256": sha256(collector.encode()).hexdigest(),
                        "scopes": ["collector:write"],
                        "enabled": True,
                    },
                    {
                        "credential_id": agent,
                        "token_sha256": sha256(agent.encode()).hexdigest(),
                        "scopes": ["agent:check"],
                        "enabled": True,
                    },
                    {
                        "credential_id": radar,
                        "token_sha256": sha256(radar.encode()).hexdigest(),
                        "scopes": ["radar:read"],
                        "enabled": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    credentials.chmod(0o600)
    settings = ApiSettings(
        environment="production",
        policy_version=POLICY_VERSION,
        bearer_tokens=(),
        max_body_bytes=1_048_576,
        idempotency_key_max_bytes=128,
        sse_heartbeat_seconds=1,
        sse_buffer_size=20,
        approval_signing_key="production-test-signing-key-at-least-32-bytes",
        exasol_required=True,
        credentials_file=credentials,
    )
    monkeypatch.setenv("SSS_RUNTIME_ROOT", os.getcwd())
    app = create_app(settings=settings)
    identity = {
        "ecosystem": "npm",
        "registry_origin": "https://registry.npmjs.org",
        "canonical_name": name,
    }
    start = datetime.now(UTC) - timedelta(days=2)
    transport = httpx.ASGITransport(app=app)
    collector_headers = {"Authorization": f"Bearer {collector}"}
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for index in range(20):
                body = {
                    "observation_id": f"model-{suffix}-{index}",
                    "package": identity,
                    "source_id": f"run-{index}",
                    "model_configuration_id": f"config-{index % 2}",
                    "observed_at": (start + timedelta(days=index % 3)).isoformat(),
                    "context_kind": "install",
                    "explicit_install_context": True,
                }
                response = await client.post(
                    "/v1/observations/model",
                    json=body,
                    headers={
                        **collector_headers,
                        "Idempotency-Key": f"{suffix}-model-{index}",
                    },
                )
                assert response.status_code == 202, response.text
            for index in range(6):
                response = await client.post(
                    "/v1/observations/client",
                    json={
                        "observation_id": f"client-{suffix}-{index}",
                        "package": identity,
                        "client_pseudonym": f"client-{suffix[:12]}-{index}",
                        "agent_family": "codex",
                        "requested_source": "registry",
                        "observed_at": (start + timedelta(days=index % 3)).isoformat(),
                    },
                    headers={
                        **collector_headers,
                        "Idempotency-Key": f"{suffix}-client-{index}",
                    },
                )
                assert response.status_code == 202, response.text
            for index in range(4):
                response = await client.post(
                    "/v1/observations/public",
                    json={
                        "observation_id": f"public-{suffix}-{index}",
                        "package": identity,
                        "public_url_sha256": sha256(f"url-{suffix}-{index}".encode()).hexdigest(),
                        "source_kind": "public_manifest",
                        "observed_at": (start + timedelta(days=index % 3)).isoformat(),
                    },
                    headers={
                        **collector_headers,
                        "Idempotency-Key": f"{suffix}-public-{index}",
                    },
                )
                assert response.status_code == 202, response.text
            for state in ("absent", "registered"):
                response = await client.post(
                    "/v1/observations/registry",
                    json={
                        "check_id": f"registry-{suffix}-{state}",
                        "package": identity,
                        "endpoint": f"https://registry.npmjs.org/{name}",
                        "status": state,
                        "http_status": 404 if state == "absent" else 200,
                        "checked_at": datetime.now(UTC).isoformat(),
                    },
                    headers={
                        **collector_headers,
                        "Idempotency-Key": f"{suffix}-registry-{state}",
                    },
                )
                assert response.status_code == 202, response.text
            connection = app.state.exasol_connection
            connection.execute(
                "INSERT INTO PACKAGE_RELEASES (RELEASE_ID, ECOSYSTEM, REGISTRY_ORIGIN, "
                "CANONICAL_NAME, VERSION, UPLOADED_AT, FIRST_SEEN_AT) VALUES ({release_id}, "
                "'npm', {origin}, {name}, '1.0.0', {uploaded_at}, {first_seen_at})",
                {
                    "release_id": f"release-{suffix}",
                    "origin": identity["registry_origin"],
                    "name": name,
                    "uploaded_at": (datetime.now(UTC) - timedelta(hours=12)).replace(tzinfo=None),
                    "first_seen_at": datetime.now(UTC).replace(tzinfo=None),
                },
            )
            connection.commit()
            guarded = await client.post(
                "/v1/check",
                json={
                    "request_id": f"request-{suffix}",
                    "project_id": "project-live",
                    "agent_family": "codex",
                    "package": identity,
                    "version_spec": "1.0.0",
                    "direct_url": None,
                    "artifact_sha256": None,
                    "is_direct": True,
                },
                headers={"Authorization": f"Bearer {agent}", "Idempotency-Key": suffix},
            )
            assert guarded.status_code == 200, guarded.text
            assert guarded.json()["decision"] == "block"
            assert guarded.json()["scores"]["target_attractiveness"] == 62
            assert guarded.json()["scores"]["package_policy_risk"] == 75
            radar_response = await client.get(
                "/v1/radar?limit=200", headers={"Authorization": f"Bearer {radar}"}
            )
            assert radar_response.status_code == 200
            assert name in {item["canonical_name"] for item in radar_response.json()["items"]}
    finally:
        connection = app.state.exasol_connection
        for table in (
            "POLICY_DECISIONS",
            "PACKAGE_RELEASES",
            "REGISTRY_CHECKS",
            "PUBLIC_SOURCE_OBSERVATIONS",
            "CLIENT_INSTALL_OBSERVATIONS",
            "PACKAGE_MENTIONS",
            "CANDIDATES",
        ):
            connection.execute(
                f"DELETE FROM {table} WHERE CANONICAL_NAME={{name}}",  # noqa: S608
                {"name": name},
            )
        connection.execute(
            "DELETE FROM INTERVENTIONS WHERE REQUEST_JSON LIKE {name_pattern}",
            {"name_pattern": f"%{name}%"},
        )
        connection.execute(
            "DELETE FROM IDEMPOTENCY_CLAIMS WHERE IDEMPOTENCY_KEY LIKE {key_pattern}",
            {"key_pattern": f"observation:%:{suffix}-%"},
        )
        connection.execute(
            "DELETE FROM CREDENTIAL_AUDIT WHERE CREDENTIAL_ID IN ({collector}, {agent}, {radar})",
            {"collector": collector, "agent": agent, "radar": radar},
        )
        connection.commit()
        connection.close()
