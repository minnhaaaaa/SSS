# Single-Organization Self-Hosted Production Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fixture-specific runtime behavior with a durable, authenticated, arbitrary-package SSS deployment that protects supported local coding agents and can be operated by one organization.

**Architecture:** Production mode requires Exasol and obtains typed evidence facts for any canonical package identity. Scoped credentials protect ingestion, Guard, Radar, intervention, and approval operations; worker and enforcement state survive restarts. Demo fixtures remain available only through an explicit demo composition.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, PyExasol, HTTPX, Typer, React 19, TypeScript, Vite, Docker Compose, Caddy, pytest, mypy, Ruff, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-13-self-hosted-production-design.md`

## Global Constraints

- Target one organization; do not add tenant IDs, billing, or public account registration.
- Production requires a production-supported external Exasol endpoint.
- Local Exasol Docker Edition remains qualification/test infrastructure only.
- Production must never import `demo/fixtures/fixed-intelligence.json` or fall back to fixture evidence.
- Registry failures remain typed `UNKNOWN`; strict noninteractive policy converts them to `BLOCK`.
- Raw service tokens, signing keys, provider keys, and proxy credentials must never be committed or logged.
- Protected agents have no direct public egress, Docker socket, Exasol credentials, canary credentials, or signing keys.
- `BLOCK` exits `23` and starts no package-manager child process.
- All SQL values are parameterized; dynamic identifiers come only from internal allowlists.
- Every public container image is digest-pinned.
- Every task ends with the named focused verification and a commit before the next task begins.

---

### Task 1: Integrate the remaining active frontend branch

**Files:**
- Merge: `origin/frontend`
- Resolve: `.env.example`, `.gitignore`, `package.json`, `pnpm-lock.yaml`, `pnpm-workspace.yaml`
- Resolve: `apps/web/src/components/app-shell.tsx`
- Resolve: `apps/web/src/components/overview-radar.tsx`
- Add: `apps/web/src/components/dock.css`
- Add: `apps/web/src/components/dock.tsx`
- Add: `apps/web/src/components/overview-radar.test.tsx`

**Interfaces:**
- Consumes: the live `/v1/public/*` client contract on `codex/agent-guard-demo`.
- Produces: the animated dock and Radar interactions from commits `a7ee502` and `3e85812` without restoring fixture-first runtime defaults.

- [ ] **Step 1: Record branch containment before merging**

Run:

```bash
git fetch --all --prune
git rev-list --left-right --count codex/agent-guard-demo...origin/frontend
git cherry codex/agent-guard-demo origin/frontend
```

Expected: `origin/frontend` has exactly two unique commits, `a7ee502` and `3e85812`; `origin/Vansh` and `codex/teammate-1-intelligence` have zero unique commits.

- [ ] **Step 2: Merge without rewriting shared history**

Run:

```bash
git merge --no-ff origin/frontend
```

Resolve root configuration in favor of the integration branch, then add only the frontend dependency and files introduced by `3e85812`. Preserve `VITE_SSS_USE_PROTOTYPE_DATA=false`, the same-origin `/v1` proxy, and the terminal-first `/demo` route.

- [ ] **Step 3: Verify the integrated frontend**

Run:

```bash
pnpm install --frozen-lockfile
pnpm test
pnpm typecheck
pnpm web:build
```

Expected: all frontend/helper tests pass, TypeScript reports zero errors, and Vite produces `apps/web/dist/index.html`.

- [ ] **Step 4: Commit the integration if conflict resolution created an uncommitted merge**

```bash
git add .env.example .gitignore package.json pnpm-lock.yaml pnpm-workspace.yaml apps/web
git commit -m "merge: integrate final frontend interactions"
```

### Task 2: Enforce explicit runtime modes

**Files:**
- Create: `packages/core/sss_core/runtime.py`
- Modify: `apps/api/sss_api/config.py`
- Modify: `apps/api/sss_api/main.py`
- Modify: `apps/api/sss_api/services/guard.py`
- Test: `tests/unit/api/test_runtime_mode.py`
- Test: `tests/unit/api/test_guard_service.py`

**Interfaces:**
- Produces: `RuntimeMode(StrEnum)`, `ApiSettings.runtime_mode`, `build_production_services(settings)`, and `ExasolEvidenceProvider`.
- Consumes: `ExasolPolicyRepository.load_facts(package)` from Task 5.

- [ ] **Step 1: Write failing runtime-separation tests**

```python
def test_production_rejects_demo_defaults() -> None:
    with pytest.raises(ConfigurationError, match="production"):
        ApiSettings.from_env({"SSS_ENV": "production", "SSS_EXASOL_REQUIRED": "false"})


def test_production_app_does_not_load_demo_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sss_api.main, "load_demo_fixture", Mock(side_effect=AssertionError))
    app = create_app(settings=production_settings(), service_factory=fake_production_services)
    assert app.state.runtime_mode is RuntimeMode.PRODUCTION
```

- [ ] **Step 2: Run the tests and confirm the fixture path is reached**

Run:

```bash
.venv/bin/pytest tests/unit/api/test_runtime_mode.py -q
```

Expected: failure because `RuntimeMode`, `runtime_mode`, and `service_factory` do not exist.

- [ ] **Step 3: Implement mode-specific composition**

```python
class RuntimeMode(StrEnum):
    PRODUCTION = "production"
    DEMO = "demo"
    TEST = "test"


def build_services(settings: ApiSettings) -> ServiceContainer:
    if settings.runtime_mode is RuntimeMode.PRODUCTION:
        return build_production_services(settings)
    if settings.runtime_mode is RuntimeMode.DEMO:
        return build_demo_services(settings)
    return build_test_services(settings)
```

Move all fixture imports and loading into `build_demo_services`. Require Exasol, a non-demo signing key, a credentials file, and the expected policy version in production.

- [ ] **Step 4: Verify mode separation and static imports**

Run:

```bash
.venv/bin/pytest tests/unit/api/test_runtime_mode.py tests/unit/api/test_guard_service.py -q
rg -n "FixedDemo|fixed-intelligence" apps/api/sss_api | grep -v production
```

Expected: tests pass and fixture references exist only in a demo composition module.

- [ ] **Step 5: Commit**

```bash
git add packages/core/sss_core/runtime.py apps/api tests/unit/api
git commit -m "refactor: isolate demo and production runtime composition"
```

### Task 3: Persist operational enforcement state in Exasol

**Files:**
- Create: `infra/exasol/migrations/002_operational_state.sql`
- Create: `packages/core/sss_core/repositories/operations.py`
- Modify: `packages/core/sss_core/repositories/exasol.py`
- Modify: `apps/api/sss_api/services/attempts.py`
- Modify: `apps/api/sss_api/services/interventions.py`
- Modify: `apps/api/sss_api/idempotency.py`
- Modify: `apps/api/sss_api/events/broker.py`
- Test: `tests/integration/test_exasol_operational_state.py`

**Interfaces:**
- Produces: `OperationalRepository.record_decision`, `record_attempt`, `create_intervention`, `resolve_intervention`, `claim_idempotency`, `append_event`, and `events_after`.
- Consumes: existing `InstallRequest`, `PolicyDecision`, approval claims, and `ExasolConnection`.

- [ ] **Step 1: Write failing repository contract tests**

```python
def test_attempt_and_intervention_survive_repository_recreation(connection) -> None:
    first = ExasolOperationalRepository(connection)
    first.record_attempt(attempt_fixture(child_started=False))
    first.create_intervention(intervention_fixture())

    second = ExasolOperationalRepository(connection)
    assert second.list_attempts(limit=10)[0].child_started is False
    assert second.list_interventions(pending_only=True)[0].package == DEMO_IDENTITY


def test_idempotency_conflict_preserves_original_response(connection) -> None:
    repository = ExasolOperationalRepository(connection)
    repository.claim_idempotency("key-1", "hash-a", "decision-a")
    with pytest.raises(IdempotencyConflict):
        repository.claim_idempotency("key-1", "hash-b", "decision-b")
    assert repository.get_idempotency("key-1").request_hash == "hash-a"
```

- [ ] **Step 2: Run against the recording connection**

Run:

```bash
.venv/bin/pytest tests/integration/test_exasol_operational_state.py -q
```

Expected: failure because migration `002_operational_state` and the repository do not exist.

- [ ] **Step 3: Add durable tables and indexes**

Migration `002_operational_state.sql` creates `INTERVENTIONS`, `IDEMPOTENCY_CLAIMS`, `EVENT_LOG`, `WORKER_JOBS`, `WORKER_LEASES`, and `CREDENTIAL_AUDIT`. Extend existing decision, attempt, and approval tables only with additive columns for request JSON, evidence-as-of, attestation, terminal state, and consumption metadata.

- [ ] **Step 4: Implement atomic repository methods**

Use bound parameters for every value. `claim_idempotency` and approval nonce consumption must execute in one transaction and roll back on conflict. `events_after` must order by numeric event ID and enforce `1 <= limit <= 1000`.

- [ ] **Step 5: Verify live migration and restart persistence**

Run:

```bash
SSS_EXASOL_DSN=127.0.0.1:8563 SSS_EXASOL_USER=sys SSS_EXASOL_PASSWORD=exasol SSS_EXASOL_SCHEMA=SSS \
  .venv/bin/pytest tests/integration/test_exasol_schema.py tests/integration/test_exasol_operational_state.py -q
```

Expected: migrations apply once, a second migration is a no-op, and enforcement state is readable through a newly constructed repository.

- [ ] **Step 6: Commit**

```bash
git add infra/exasol packages/core/sss_core/repositories apps/api/sss_api tests/integration
git commit -m "feat: persist guard operational state in exasol"
```

### Task 4: Add scoped, digest-backed authentication

**Files:**
- Create: `packages/core/sss_core/auth.py`
- Create: `apps/cli/sss_cli/admin.py`
- Modify: `apps/api/sss_api/config.py`
- Modify: `apps/api/sss_api/security.py`
- Modify: `apps/api/sss_api/main.py`
- Modify: `apps/cli/sss_cli/main.py`
- Test: `tests/security/test_scoped_auth.py`
- Test: `tests/unit/cli/test_admin_tokens.py`

**Interfaces:**
- Produces: `CredentialRecord`, `CredentialStore.authenticate(raw_token, required_scope)`, `require_scope(scope)`, and `sss admin token generate`.
- Consumes: `SSS_CREDENTIALS_FILE` containing `{ "credentials": [...] }`.

- [ ] **Step 1: Write failing scope and token-generation tests**

```python
def test_agent_token_cannot_read_private_radar(client) -> None:
    response = client.get("/v1/radar", headers=bearer("agent-raw-token"))
    assert response.status_code == 403


def test_token_generator_outputs_digest_not_raw_token_in_record() -> None:
    generated = generate_token("agent-01", frozenset({"agent:check"}))
    assert generated.raw_token not in json.dumps(generated.record.to_json())
    assert generated.record.token_sha256 == sha256(generated.raw_token.encode()).hexdigest()
```

- [ ] **Step 2: Confirm existing bearer-token authentication fails scope tests**

Run:

```bash
.venv/bin/pytest tests/security/test_scoped_auth.py tests/unit/cli/test_admin_tokens.py -q
```

Expected: failure because tokens have no identity or scopes.

- [ ] **Step 3: Implement credential parsing and constant-time authentication**

```python
@dataclass(frozen=True, slots=True)
class CredentialRecord:
    credential_id: str
    token_sha256: str
    scopes: frozenset[str]
    enabled: bool


def require_scope(scope: str):
    async def dependency(request: Request) -> CredentialPrincipal:
        return request.app.state.credentials.authenticate_bearer(request, scope)
    return dependency
```

Validate unique credential IDs, lowercase 64-character digests, known scopes, secure file permissions, and disabled credentials. Record credential ID, route, outcome, request ID, and time without recording the token.

- [ ] **Step 4: Apply exact scopes to all private routes**

Guard requires `agent:check`; observation ingestion requires `collector:write`; Radar requires `radar:read`; approval creation requires `approval:write`; intervention resolution requires `operator:intervene`.

- [ ] **Step 5: Verify authentication and secret hygiene**

Run:

```bash
.venv/bin/pytest tests/security/test_scoped_auth.py tests/unit/cli/test_admin_tokens.py -q
.venv/bin/ruff check packages/core/sss_core/auth.py apps/api/sss_api/security.py apps/cli/sss_cli/admin.py tests/security/test_scoped_auth.py
```

Expected: missing tokens return `401`, wrong scopes return `403`, disabled tokens return `401`, valid scopes pass, and generated records contain no raw token.

- [ ] **Step 6: Commit**

```bash
git add packages/core/sss_core/auth.py apps/api apps/cli tests/security tests/unit/cli
git commit -m "feat: enforce scoped service credentials"
```

### Task 5: Generalize evidence, scoring, ingestion, and private reads

**Files:**
- Create: `packages/core/sss_core/evidence/facts.py`
- Create: `apps/api/sss_api/schemas/observations.py`
- Create: `apps/api/sss_api/routes/observations.py`
- Create: `apps/api/sss_api/routes/radar.py`
- Modify: `packages/core/sss_core/repositories/exasol.py`
- Modify: `apps/api/sss_api/services/guard.py`
- Modify: `apps/api/sss_api/main.py`
- Test: `tests/integration/test_production_guard.py`
- Test: `tests/integration/test_observation_api.py`
- Test: `tests/integration/test_private_radar_api.py`

**Interfaces:**
- Produces: `EvidenceFacts`, `ExasolPolicyRepository.load_facts(package)`, `ExasolEvidenceProvider.context_for(package)`, `/v1/observations/{model,client,public,registry}`, and paginated `/v1/radar` APIs.
- Consumes: canonical scoring functions and scoped authentication from Task 4.

- [ ] **Step 1: Write failing arbitrary-package Guard tests**

```python
def test_production_guard_scores_an_arbitrary_transition(exasol_client) -> None:
    identity = PackageIdentity(Ecosystem.NPM, "https://registry.npmjs.org", "novel-agent-tool")
    seed_general_evidence(exasol_client, identity, runs=20, models=2, clients=6, sources=4, days=3)
    decision = post_guard_check(identity, version="1.0.0")
    assert decision["decision"] == "block"
    assert decision["scores"]["target_attractiveness"] == 62
    assert "REGISTERED_AFTER_HALLUCINATION" in decision["reason_codes"]
```

- [ ] **Step 2: Write strict ingestion tests**

Test provenance assignment, unknown-field rejection, idempotent duplicate writes, conflicting idempotency keys, invalid origins, client telemetry redaction, and public-name suppression.

- [ ] **Step 3: Run focused tests and confirm fixture coupling**

Run:

```bash
.venv/bin/pytest tests/integration/test_production_guard.py tests/integration/test_observation_api.py tests/integration/test_private_radar_api.py -q
```

Expected: failure because the production provider and routes are absent.

- [ ] **Step 4: Implement typed fact conversion and scoring**

```python
@dataclass(frozen=True, slots=True)
class EvidenceFacts:
    candidate_status: CandidateStatus
    registry_outcome: RegistryOutcome
    conclusive_absence: bool
    exclusions_complete: bool
    distinct_verified_runs: int
    distinct_model_configurations: int
    distinct_clients: int
    distinct_public_sources: int
    distinct_observation_days: int
    explicit_install_context: bool
    first_release_age_hours: float | None
    source_policy_violation: bool
    suspicious_static_finding: bool
    data_as_of: datetime
```

`ExasolEvidenceProvider` converts facts to `AttractivenessInputs` and `PolicyRiskInputs`, calls the canonical scoring functions, and creates `PolicyContext`. Missing rows yield typed unknown evidence and strict blocking rather than fixture fallback.

- [ ] **Step 5: Implement authenticated routes and pagination**

Use Pydantic models with `extra="forbid"`. Assign provenance server-side. Private list routes accept `limit` from 1 through 200 and an opaque cursor composed of stable sort time plus identifier.

- [ ] **Step 6: Verify general data flow**

Run:

```bash
.venv/bin/pytest tests/integration/test_production_guard.py tests/integration/test_observation_api.py tests/integration/test_private_radar_api.py tests/security/test_telemetry_redaction.py -q
.venv/bin/mypy packages/core apps/api
```

Expected: two unrelated npm/PyPI identities produce different computed scores, private routes require scope, and public aggregates contain no absent names.

- [ ] **Step 7: Commit**

```bash
git add packages/core/sss_core/evidence packages/core/sss_core/repositories apps/api tests
git commit -m "feat: assess arbitrary exasol package evidence"
```

### Task 6: Make collectors runnable and durable

**Files:**
- Create: `apps/worker/sss_worker/config.py`
- Create: `apps/worker/sss_worker/main.py`
- Create: `apps/worker/sss_worker/providers/openai_compatible.py`
- Create: `apps/worker/sss_worker/repository.py`
- Modify: `apps/worker/sss_worker/scheduler.py`
- Modify: `apps/worker/sss_worker/jobs/probe.py`
- Modify: `apps/worker/sss_worker/jobs/github.py`
- Modify: `apps/worker/sss_worker/jobs/recheck.py`
- Test: `tests/integration/test_worker_runtime.py`
- Test: `tests/unit/test_openai_compatible_provider.py`
- Test: `tests/unit/test_worker_leases.py`

**Interfaces:**
- Produces: `sss-worker run`, `sss-worker once JOB_NAME`, `OpenAICompatibleProvider.complete`, and durable `WorkerRepository` cursors/leases.
- Consumes: observation repositories, registry oracles, `SSS_MODEL_BASE_URL`, and a provider-token secret file.

- [ ] **Step 1: Write failing provider boundary tests**

```python
@respx.mock
def test_provider_records_exact_model_and_hashes_without_logging_body(caplog) -> None:
    respx.post("http://model.internal/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "Use novel-lib"}}]})
    )
    result = provider.complete(task_fixture())
    assert result.model_id == "local-code-model"
    assert len(result.response_sha256) == 64
    assert "Use novel-lib" not in caplog.text
```

- [ ] **Step 2: Write failing lease/cursor tests**

Prove one worker obtains a job lease, a concurrent worker is rejected, expired leases can be reclaimed, successful runs advance cursors, and failed/rate-limited runs preserve cursors.

- [ ] **Step 3: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/unit/test_openai_compatible_provider.py tests/unit/test_worker_leases.py tests/integration/test_worker_runtime.py -q
```

Expected: failure because no executable worker or durable repository exists.

- [ ] **Step 4: Implement validated configuration and entrypoints**

Require an HTTPS model URL in production unless the hostname is loopback/private and `SSS_ALLOW_PRIVATE_HTTP_MODEL=true`. Read the provider token from `SSS_MODEL_TOKEN_FILE`. Bound request timeouts, response bytes, concurrency, and retry attempts.

- [ ] **Step 5: Implement durable scheduling**

Run the existing intervals from `build_schedule`. Acquire a lease before each job, heartbeat long runs, persist typed outcome and freshness time, and release the lease in `finally`. Never run replay automatically in production.

- [ ] **Step 6: Verify worker restart behavior**

Run:

```bash
.venv/bin/pytest tests/unit/test_openai_compatible_provider.py tests/unit/test_worker_leases.py tests/integration/test_worker_runtime.py -q
.venv/bin/mypy apps/worker
```

Expected: a restarted worker resumes the stored cursor and duplicate source events do not increase recurrence.

- [ ] **Step 7: Commit**

```bash
git add apps/worker tests/unit/test_openai_compatible_provider.py tests/unit/test_worker_leases.py tests/integration/test_worker_runtime.py pyproject.toml uv.lock
git commit -m "feat: run durable production intelligence collectors"
```

### Task 7: Protect arbitrary supported package-manager commands

**Files:**
- Create: `apps/cli/sss_cli/shims/pip`
- Create: `apps/cli/sss_cli/shims/pip3`
- Create: `apps/cli/sss_cli/shims/python`
- Create: `apps/cli/sss_cli/shims/uv`
- Create: `apps/cli/sss_cli/shims/poetry`
- Create: `apps/cli/sss_cli/shims/npm`
- Create: `apps/cli/sss_cli/shims/yarn`
- Create: `apps/cli/sss_cli/shims/npx`
- Create: `apps/cli/sss_cli/config_file.py`
- Modify: `apps/cli/sss_cli/shim.py`
- Modify: `apps/cli/sss_cli/adapters.py`
- Modify: `apps/cli/sss_cli/main.py`
- Modify: `infra/docker/agent.Dockerfile`
- Test: `tests/security/test_all_client_non_execution.py`
- Test: `tests/e2e/test_generic_agent_protection.py`
- Test: `tests/unit/cli/test_config_file.py`

**Interfaces:**
- Produces: one common `run_shim(client_name, argv, environment)` path, `sss configure --server URL --token-file PATH`, and `sss protect -- AGENT_ARGV` for arbitrary agent executables.
- Consumes: existing extraction adapters, Guard API, gateway URL, and immutable executable map.

- [ ] **Step 1: Add a parametrized failing non-execution matrix**

```python
@pytest.mark.parametrize(
    ("client", "argv"),
    [
        ("pip", ["install", "novel-lib"]),
        ("pip3", ["install", "novel-lib"]),
        ("python", ["-m", "pip", "install", "novel-lib"]),
        ("uv", ["add", "novel-lib"]),
        ("poetry", ["add", "novel-lib"]),
        ("npm", ["install", "novel-lib"]),
        ("pnpm", ["add", "novel-lib"]),
        ("yarn", ["add", "novel-lib"]),
        ("npx", ["novel-lib"]),
    ],
)
def test_blocked_client_never_starts_child(client, argv, recording_backend) -> None:
    assert run_shim(client, argv, backend=recording_backend, guard=blocking_guard) == 23
    assert recording_backend.calls == []
```

- [ ] **Step 2: Add allow-path and hostile-input cases**

For every client, prove an established approved registry package starts the immutable real executable exactly once. Prove shell metacharacters remain argv data, and direct URL, Git, path, alternate registry, missing hash, parse failure, and Guard outage start no child.

Add `test_config_file.py` cases proving configuration is written with mode `0600`, accepts only
absolute HTTPS servers except explicit loopback HTTP, reads the raw token from a separate `0600`
file, and never includes token contents in exceptions or CLI output.

- [ ] **Step 3: Run the matrix and confirm missing shims**

Run:

```bash
.venv/bin/pytest tests/security/test_all_client_non_execution.py tests/e2e/test_generic_agent_protection.py -q
```

Expected: failure for every client except the existing `pnpm` path.

- [ ] **Step 4: Implement common shim dispatch**

Each executable shim contains only:

```python
#!/usr/bin/env python3
from sss_cli.shim import main_for_executable

main_for_executable()
```

Derive the client from `argv[0]`, dispatch to the existing safe parser, send one Guard request per direct requirement, and start the immutable executable only when every decision allows it. The `python` shim delegates unchanged unless argv begins with `-m pip`.

Implement `sss configure` by writing server URL, token-file path, organization ID, and project ID
to `${XDG_CONFIG_HOME}/sss/config.json` using an atomic temporary-file rename. Refuse token values
on the command line; `--token-file` is required so shell history never contains the credential.

- [ ] **Step 5: Update the protected image and gateway-only client configuration**

Copy all shims with mode `0555`. Configure pip/npm family clients to use only the gateway. Remove package-manager configuration that permits public fallback.

- [ ] **Step 6: Verify the complete client matrix**

Run:

```bash
.venv/bin/pytest tests/security/test_all_client_non_execution.py tests/security/test_command_parsing.py tests/e2e/test_generic_agent_protection.py tests/unit/cli/test_config_file.py -q
docker build -f infra/docker/agent.Dockerfile --build-arg SSS_NODE_BASE_IMAGE="$SSS_NODE_BASE_IMAGE" --build-arg SSS_PYTHON_BASE_IMAGE="$SSS_PYTHON_BASE_IMAGE" -t sss-agent:production-test .
docker run --rm --network none --user 65532:65532 --entrypoint /usr/local/bin/pnpm sss-agent:production-test --version
```

Expected: all blocked paths return `23` with zero child starts; allowed paths execute once; the networkless pnpm version check succeeds.

- [ ] **Step 7: Commit**

```bash
git add apps/cli infra/docker/agent.Dockerfile tests/security/test_all_client_non_execution.py tests/e2e/test_generic_agent_protection.py
git commit -m "feat: protect all supported package manager clients"
```

### Task 8: Replace fixture UI APIs with authenticated private repositories

**Files:**
- Modify: `apps/api/sss_api/routes/public.py`
- Modify: `apps/api/sss_api/routes/radar.py`
- Modify: `apps/web/src/api/control-room.ts`
- Modify: `apps/web/src/api/events.ts`
- Modify: `apps/web/src/app/services.ts`
- Modify: `apps/web/src/pages/demo-page.tsx`
- Modify: `apps/web/src/pages/radar-page.tsx`
- Modify: `apps/web/src/pages/decisions-page.tsx`
- Test: `tests/integration/test_public_aggregate_api.py`
- Test: `apps/web/src/api/control-room.test.ts`
- Test: `apps/web/src/components/overview-radar.test.tsx`

**Interfaces:**
- Produces: repository-backed `/v1/radar`, `/v1/packages`, `/v1/decisions`, `/v1/coverage`, `/v1/events`, and redacted `/v1/public/aggregates`.
- Consumes: private pagination and durable event IDs from Tasks 3 and 5.

- [ ] **Step 1: Write failing no-fixture API tests**

```python
async def test_private_radar_returns_seeded_arbitrary_rows(production_app) -> None:
    response = await client.get("/v1/radar?limit=20", headers=radar_headers())
    assert [item["name"] for item in response.json()["items"]] == ["novel-agent-tool", "safe-lib"]
    assert "@sss-demo/reserved-synthetic" not in response.text
```

Test `Last-Event-ID` resumption after a new application instance and prove public aggregates cannot enumerate private absent identities.

- [ ] **Step 2: Run API and web tests**

Run:

```bash
.venv/bin/pytest tests/integration/test_public_aggregate_api.py tests/integration/test_private_radar_api.py -q
pnpm --filter @sss/web test
```

Expected: failure because live frontend parsing targets synthetic `/v1/public/*` routes.

- [ ] **Step 3: Implement repository-backed contracts**

Keep TypeScript runtime validation. Add pagination fields `{items, next_cursor, data_as_of}`. Production UI calls private same-origin routes through Caddy; demo mode retains the current synthetic service behind `VITE_SSS_USE_PROTOTYPE_DATA=true` or the explicit demo deployment.

- [ ] **Step 4: Verify UI behavior and accessibility**

Run:

```bash
pnpm --filter @sss/web test
pnpm typecheck
pnpm web:build
```

Then exercise desktop `1440x900` and narrow `390x844` layouts in Chrome. Confirm keyboard navigation, visible focus, no horizontal overflow, reduced-motion behavior, correct loading/empty/stale/offline/error states, and no mutation request from the browser.

- [ ] **Step 5: Commit**

```bash
git add apps/api/sss_api/routes apps/web tests/integration
git commit -m "feat: serve private radar from exasol evidence"
```

### Task 9: Add production composition and recoverable operations

**Files:**
- Create: `infra/docker/production.compose.yaml`
- Create: `infra/docker/Caddyfile.production`
- Create: `infra/docker/web.Dockerfile`
- Create: `scripts/backup_exasol.py`
- Create: `scripts/restore_exasol.py`
- Create: `scripts/production_readiness.py`
- Create: `docs/operations/self-hosted-production.md`
- Modify: `.env.example`
- Modify: `README.md`
- Test: `tests/security/test_production_compose.py`
- Test: `tests/integration/test_backup_restore.py`

**Interfaces:**
- Produces: one `production` Compose profile connecting to external Exasol and one documented local qualification profile.
- Consumes: API, worker, web, gateway, Caddy auth, credentials file, signing secret, and Exasol connection settings.

- [x] **Step 1: Write failing production composition tests**

```python
def test_production_exposes_only_tls_proxy(compose_config) -> None:
    exposed = {name for name, service in compose_config["services"].items() if service.get("ports")}
    assert exposed == {"proxy"}
    assert compose_config["services"]["api"]["environment"]["SSS_ENV"] == "production"
    assert "exasol" not in compose_config["services"]


def test_agent_has_only_guard_and_gateway_network(compose_config) -> None:
    agent = compose_config["services"]["protected-agent"]
    assert agent["cap_drop"] == ["ALL"]
    assert agent["read_only"] is True
    assert "/var/run/docker.sock" not in json.dumps(agent)


def test_proxy_overwrites_trusted_identity_headers(caddy_adapter) -> None:
    response = caddy_adapter.get(
        "/v1/radar",
        headers={"X-SSS-Operator": "forged", "X-SSS-Proxy-Token": "forged"},
        auth=("operator", "correct-password"),
    )
    assert response.status_code == 200
    assert response.request.headers["X-SSS-Operator"] == "operator"
```

- [x] **Step 2: Write failing backup/restore equivalence test**

Seed a disposable schema with evidence, one decision, one event, one pending intervention, and one consumed approval. Export it, restore into a second disposable schema, and compare migration version, per-table counts, and decision attestation.

- [x] **Step 3: Run focused tests**

Run:

```bash
.venv/bin/pytest tests/security/test_production_compose.py tests/integration/test_backup_restore.py -q
```

Expected: failure because production Compose and operational scripts do not exist.

- [x] **Step 4: Implement the production profile**

Pin application base images and Caddy by digest. Add health checks, restart policies, resource limits, log rotation, internal networks, read-only roots, secret-file mounts, and no host ports except TLS proxy `8443:443`. Require external Exasol DSN and TLS certificate/key files. Configure Caddy Basic authentication from a bcrypt secret file, remove incoming trusted identity headers, and inject the authenticated user plus proxy token. Do not include demo, canary, registry seed, or local Exasol services.

- [x] **Step 5: Implement backup, restore, and readiness commands**

Backup writes a manifest containing schema version, UTC time, table counts, export file hashes, and application version. Restore refuses a nonempty target schema unless `--allow-nonempty` is explicitly supplied. Readiness verifies TLS, API readiness, worker freshness, Exasol migration checksums, policy version, gateway configuration, and credential scopes without printing secrets.

- [x] **Step 6: Verify clean self-hosted startup**

Run:

```bash
docker compose --env-file .env.production -f infra/docker/production.compose.yaml config --quiet
.venv/bin/pytest tests/security/test_production_compose.py tests/integration/test_backup_restore.py -q
.venv/bin/python scripts/production_readiness.py --base-url https://127.0.0.1:8443
```

Expected: Compose renders without demo services, the disposable backup round trip passes, and readiness reports every required component healthy.

- [x] **Step 7: Commit**

```bash
git add infra/docker scripts docs/operations/self-hosted-production.md .env.example README.md tests
git commit -m "feat: ship recoverable self-hosted production profile"
```

### Task 10: Complete security, release, branch, and main integration gates

**Files:**
- Modify: `scripts/validate_local.sh`
- Create: `scripts/validate_production.sh`
- Modify: `PLAN.md`
- Modify: `README.md`
- Modify: `docs/contracts/CHANGELOG.md`
- Create: `docs/pitch/SSS-pitch-deck.pptx`
- Create: `docs/pitch/SSS-pitch-deck.pdf`
- Create: `docs/pitch/README.md`
- Create: `docs/demo-video-script.md`
- Create: `scripts/build_pitch_deck.mjs`
- Create: `CHANGELOG.md`

**Interfaces:**
- Produces: a reproducible release gate and integrated `main` branch.
- Consumes: all tasks and every active remote branch.

- [x] **Step 1: Complete the submission package**

Rewrite the root README as the submission entry point with the problem, solution, architecture, supported agent/package-manager integrations, zero-cost local demo setup, production self-hosted deployment, usage, validation, security boundary, pitch-deck links, and a clearly labeled demo-video link. Create an editable pitch deck plus PDF export, its reproducible build source, and a timed demo-video script. The video workflow must show a real agent issuing an install request, SSS blocking a slopsquatted package before the child process starts, operator intervention with exact approval scope, and a successful authorized retry. Do not present the dashboard as the primary demo. If the final hosted video URL is not available, use one conspicuous `DEMO_VIDEO_URL` placeholder and document the single replacement step; do not invent a URL.

- [x] **Step 2: Add the complete validation driver**

`scripts/validate_production.sh` runs frozen dependency installation, all unit/integration/security/E2E tests, live Exasol tests, mypy, Ruff, Node tests/typecheck/build, Docker Compose rendering, the client interception matrix, browser checks, dependency audits, secret scan, available image scan, backup/restore, and two protected-agent rehearsals.

- [x] **Step 3: Run the complete release gate**

Run:

```bash
./scripts/validate_production.sh
git diff --check
```

Expected: exit `0`; two protected rehearsals return `23`; neither increments the canary; no unresolved high-severity dependency or image finding remains.

- [x] **Step 4: Refresh and reconcile branches again**

Run:

```bash
git fetch --all --prune
git for-each-ref --sort=-committerdate --format='%(refname:short) %(objectname:short) %(subject)' refs/heads refs/remotes/origin
git cherry codex/agent-guard-demo origin/frontend
git cherry codex/agent-guard-demo origin/Vansh
git cherry codex/agent-guard-demo codex/teammate-1-intelligence
```

Expected: no `+` commits remain on project implementation branches. Review any newly created remote branch before proceeding.

- [x] **Step 5: Document the release boundary**

Update the contract changelog for new scopes, pagination, runtime mode, and persistence. Add a `0.2.0` changelog entry covering production deployment, arbitrary package evidence, durable enforcement, supported clients, security boundaries, and the explicit Exasol licensing/deployment limitation.

- [x] **Step 6: Commit the release gate**

```bash
git add scripts PLAN.md README.md docs/contracts/CHANGELOG.md docs/pitch docs/demo-video-script.md CHANGELOG.md
git commit -m "chore: enforce production release gates"
```

- [x] **Step 7: Re-run validation from the exact integration commit**

Run:

```bash
./scripts/validate_production.sh
git status --short
```

Expected: exit `0` and an empty status.

- [ ] **Step 8: Merge into main without discarding user work**

Verify `/home/minnhaaaaa/Documents/exasol/SSS` is clean, then run:

```bash
git -C /home/minnhaaaaa/Documents/exasol/SSS fetch origin
git -C /home/minnhaaaaa/Documents/exasol/SSS merge --no-ff codex/agent-guard-demo
```

Run `./scripts/validate_production.sh` from the main worktree. If it passes, push with:

```bash
git -C /home/minnhaaaaa/Documents/exasol/SSS push origin main
```

Expected: local `main`, `origin/main`, and `codex/agent-guard-demo` resolve to histories containing the complete production integration; no force push occurs.
