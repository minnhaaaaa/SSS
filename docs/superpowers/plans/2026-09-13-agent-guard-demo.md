# Agent Guard Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic terminal-first demo where a protected coding agent attempts an
unsafe `pnpm add`, SSS blocks before `pnpm` starts, and a separate operator receives an intervention.

**Architecture:** Merge the intelligence and enforcement branches into one monorepo, expose a thin
Guard/intervention API over the frozen core policy, and put an SSS command shim in front of the real
package manager. A deterministic agent fixture exercises the same `sss protect -- <agent>` boundary
as a real agent, while Exasol supplies the frozen evidence and a local canary proves non-execution.

**Tech Stack:** Python 3.12, FastAPI, Typer, Rich, httpx, Exasol, Docker Compose, pnpm, pytest,
Vitest, strict mypy and Ruff.

**Spec:** `docs/superpowers/specs/2026-09-13-agent-guard-demo-design.md`

## Global Constraints

- Policy version is exactly `sss-hackathon-v3`.
- Demo package identity is npm `@sss-demo/reserved-synthetic` at
  `https://npm.demo.sss.test`.
- Demo values remain `46/3/8/5/11`, scores remain `100/95/75`, and the transition age remains
  43 minutes.
- The noninteractive agent never sees an approval/signing credential and never receives a prompt.
- `BLOCK` returns exit code `23`; blocked commands start zero package-manager children.
- Shell strings are never evaluated; all subprocesses use argument vectors and `shell=False`.
- `Keep blocked` is the default for EOF, invalid input, no TTY and operator disconnection.
- Local Linux runs use Exasol Docker Edition and must not be described as Exasol Personal.
- No cloud resources may be provisioned by this plan.

---

### Task 1: Integrate the intelligence and enforcement branches

**Files:**
- Modify: `.env.example`
- Modify: `.gitignore`
- Modify: `package.json`
- Modify: `pnpm-workspace.yaml`
- Modify: `pyproject.toml`
- Regenerate: `pnpm-lock.yaml`
- Regenerate: `uv.lock`
- Modify: `docs/contracts/CHANGELOG.md`

**Interfaces:**
- Consumes: `codex/teammate-1-intelligence`, `origin/Vansh`, and recovered UI commit `8d2c28e`.
- Produces: one importable Python environment containing `sss_core`, `sss_worker`, `sss_api`,
  `sss_cli`, `sss_gateway`, and `sss_canary`; one pnpm workspace containing the npm parser and web.

- [ ] **Step 1: Merge `origin/Vansh` without committing**

Run:

```bash
git merge --no-commit --no-ff origin/Vansh
```

Expected: seven add/add conflicts only in the root configuration and lock files.

- [ ] **Step 2: Resolve root project configuration**

Keep all runtime packages under setuptools package discovery and add the core dependencies
`packaging`, `pyexasol`, `pyyaml` and `tenacity` to the enforcement dependencies. Configure pytest
with Python paths for `packages/core`, `apps/worker`, all service apps and `demo/canary`. Configure
strict mypy for all six Python packages. Merge every environment key while keeping demo credentials
empty and keeping `VITE_SSS_USE_PROTOTYPE_DATA=false` as the integrated default.

- [ ] **Step 3: Regenerate lock files**

Run:

```bash
UV_CACHE_DIR=/tmp/sss-agent-guard-uv uv lock
pnpm install --lockfile-only
```

Expected: dependency resolution succeeds without removing either workspace package.

- [ ] **Step 4: Run the merged regression suite**

Run:

```bash
UV_CACHE_DIR=/tmp/sss-agent-guard-uv uv sync --frozen --all-groups
UV_CACHE_DIR=/tmp/sss-agent-guard-uv uv run pytest -q -m "not docker"
UV_CACHE_DIR=/tmp/sss-agent-guard-uv uv run mypy packages/core apps/worker apps/api apps/cli apps/gateway demo/canary
UV_CACHE_DIR=/tmp/sss-agent-guard-uv uv run ruff check .
pnpm test
pnpm typecheck
```

Expected: all pre-existing non-Docker tests, type checks and linters pass.

- [ ] **Step 5: Record the interface integration**

Add a changelog entry stating that the enforcement apps consume the frozen Teammate 1 domain,
approval and fixture contracts without changing their semantics.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: integrate intelligence and enforcement foundations"
```

---

### Task 2: Add the Guard assessment and intervention service

**Files:**
- Create: `apps/api/sss_api/schemas/guard.py`
- Create: `apps/api/sss_api/services/guard.py`
- Create: `apps/api/sss_api/services/interventions.py`
- Create: `apps/api/sss_api/routes/guard.py`
- Create: `apps/api/sss_api/routes/interventions.py`
- Modify: `apps/api/sss_api/main.py`
- Modify: `apps/api/sss_api/config.py`
- Test: `tests/unit/api/test_guard_service.py`
- Test: `tests/integration/test_guard_api.py`

**Interfaces:**
- Consumes: `PolicyEngine.assess(InstallRequest, PolicyContext) -> PolicyDecision`,
  `FixedDemoFixture`, and `EventBroker.publish(event_type, payload)`.
- Produces: `GuardService.check(request: InstallRequest) -> GuardAssessment`,
  `InterventionStore.create(assessment) -> Intervention`, and authenticated `/v1/check` plus
  `/v1/interventions` routes.

- [ ] **Step 1: Write failing service tests**

Create tests with an in-memory evidence provider returning
`CandidateStatus.REGISTERED_AFTER_ABSENCE`, `RegistryOutcome.REGISTERED`, scores
`EvidenceScores(100, 95, 75)`, approved source and historical hallucination. Assert the service
returns block reasons `REGISTERED_AFTER_HALLUCINATION` and `HIGH_GLOBAL_RECURRENCE`, creates one
pending intervention, and publishes one `install.blocked` event.

- [ ] **Step 2: Verify red state**

Run:

```bash
uv run pytest tests/unit/api/test_guard_service.py -v
```

Expected: import failure for `sss_api.services.guard`.

- [ ] **Step 3: Implement strict Pydantic request/response schemas**

Use `ConfigDict(extra="forbid")`. Convert the API request into the frozen `PackageIdentity` and
`InstallRequest`; serialize `PolicyDecision` with nested scores and uppercase reason codes.

- [ ] **Step 4: Implement the service and in-memory intervention store**

Define immutable `GuardAssessment` and `Intervention` dataclasses. Assign intervention IDs from the
decision ID, retain ordered evidence labels, and publish only allowlisted event fields. The store
must support `list_pending`, `get`, `keep_blocked` and `resolve_approved` under a lock.

- [ ] **Step 5: Write failing route tests**

Assert `/v1/check` requires bearer auth and an idempotency key, rejects extra JSON fields, returns
the frozen `100/95/75` block, and makes the new intervention visible to an authenticated operator.
Assert a repeated idempotency key returns the same decision without a duplicate intervention.

- [ ] **Step 6: Implement routes and dependencies**

Compose demo-backed dependencies in `create_app` while keeping constructors injectable for tests.
Register `/v1/check`, `/v1/install-attempts`, `/v1/interventions`, detail and keep-blocked routes.

- [ ] **Step 7: Verify green state**

Run:

```bash
uv run pytest tests/unit/api/test_guard_service.py tests/integration/test_guard_api.py -v
uv run mypy apps/api
uv run ruff check apps/api tests/unit/api tests/integration/test_guard_api.py
```

Expected: all focused tests and checks pass.

- [ ] **Step 8: Commit**

```bash
git add apps/api tests/unit/api/test_guard_service.py tests/integration/test_guard_api.py
git commit -m "feat: expose guard decisions and human interventions"
```

---

### Task 3: Implement the package-manager Guard runner and pnpm shim

**Files:**
- Create: `apps/cli/sss_cli/adapters.py`
- Create: `apps/cli/sss_cli/guard.py`
- Create: `apps/cli/sss_cli/shim.py`
- Create: `apps/cli/sss_cli/shims/pnpm`
- Modify: `apps/cli/sss_cli/main.py`
- Modify: `apps/cli/sss_cli/config.py`
- Test: `tests/unit/cli/test_guard.py`
- Test: `tests/security/test_no_child_process.py`

**Interfaces:**
- Consumes: `extract_npm_mentions(text)`, `/v1/check`, `/v1/install-attempts`, an absolute real
  executable map, and original `Sequence[str]` argv.
- Produces: `parse_install_argv(argv: Sequence[str]) -> tuple[InstallRequest, ...]`,
  `GuardRunner.run(manager: str, argv: Sequence[str]) -> int`, and executable `pnpm` shim.

- [ ] **Step 1: Write failing parser and zero-spawn tests**

For `("pnpm", "add", "@sss-demo/reserved-synthetic@1.0.0")`, assert one request with canonical
name, exact version, configured registry, project and agent. Use a recording process backend and a
fake Guard client returning `BLOCK`; assert return code `23`, zero backend calls and attempt record
`child_started=false`.

- [ ] **Step 2: Verify red state**

Run:

```bash
uv run pytest tests/unit/cli/test_guard.py tests/security/test_no_child_process.py -v
```

Expected: import failures for the new CLI modules.

- [ ] **Step 3: Implement adapters and Guard HTTP client**

Reject shell operators, alternate origins, VCS URLs, direct URLs and local paths. Require an exact
version and artifact SHA-256 in strict demo mode. Send bearer and idempotency headers. Treat timeout,
connection failure and invalid response as assessment unavailable, never as allow.

- [ ] **Step 4: Implement runner and terminal output**

Print package, origin, three scores, reason codes, intervention ID and the exact sentence
`Installation was not started.` for block. Only call the absolute real executable after every
request is allowed. Record the actual spawn outcome.

- [ ] **Step 5: Install the pnpm shim entrypoint**

The entrypoint calls `python -m sss_cli.shim pnpm "$@"`. Validate that the configured real path is
absolute and does not resolve into the shim directory.

- [ ] **Step 6: Verify green and hostile cases**

Run:

```bash
uv run pytest tests/unit/cli/test_guard.py tests/security/test_no_child_process.py tests/security/test_command_parsing.py -v
uv run mypy apps/cli
uv run ruff check apps/cli tests/unit/cli tests/security/test_no_child_process.py
```

Expected: block path has zero child starts; established allow path has exactly one child start with
the original argument vector.

- [ ] **Step 7: Commit**

```bash
git add apps/cli tests/unit/cli tests/security/test_no_child_process.py
git commit -m "feat: intercept pnpm installs before execution"
```

---

### Task 4: Add operator intervention and exact-scope approval commands

**Files:**
- Create: `apps/api/sss_api/services/approvals.py`
- Create: `apps/api/sss_api/routes/approvals.py`
- Create: `apps/cli/sss_cli/intervene.py`
- Modify: `apps/cli/sss_cli/main.py`
- Modify: `apps/api/sss_api/main.py`
- Test: `tests/security/test_api_approvals.py`
- Test: `tests/unit/cli/test_intervene.py`

**Interfaces:**
- Consumes: `ApprovalScope`, pending `Intervention`, operator bearer token and SSE/REST events.
- Produces: HMAC-signed single-use grants, `/v1/approvals`, atomic consume endpoint, and
  `sss intervene --watch`.

- [ ] **Step 1: Write failing approval API tests**

Issue a grant for the frozen package, `1.0.0`, logical origin, 64-character artifact hash,
`project-demo`, five-minute expiry, nonce and active policy. Assert altered version/hash/project,
expiry and second consumption fail. Assert the signing key never appears in a response or event.

- [ ] **Step 2: Verify red state**

Run:

```bash
uv run pytest tests/security/test_api_approvals.py -v
```

Expected: missing approvals service and routes.

- [ ] **Step 3: Implement signer and one-time store**

Canonicalize claims with sorted compact JSON, sign them with HMAC-SHA256, compare signatures with
`compare_digest`, and atomically mark a nonce consumed under a lock. Reject missing signing key at
startup outside explicit test injection.

- [ ] **Step 4: Write failing operator CLI tests**

Feed one pending intervention and simulated inputs `i`, `k`, `a`, EOF and invalid text. Assert
inspect prints ordered evidence, keep-blocked resolves safely, allow-once sends the exact scope, and
EOF/invalid input never creates an approval.

- [ ] **Step 5: Implement `sss intervene`**

Use REST reconciliation before waiting for SSE. Render the intervention with Rich, default to keep
blocked, and reconnect using the last event ID. `--once` handles one intervention for deterministic
recording; `--watch` continues.

- [ ] **Step 6: Verify focused suites**

Run:

```bash
uv run pytest tests/security/test_api_approvals.py tests/unit/cli/test_intervene.py -v
uv run mypy apps/api apps/cli
uv run ruff check apps/api apps/cli tests/security/test_api_approvals.py tests/unit/cli/test_intervene.py
```

Expected: exact-scope approval cannot be widened or replayed; intervention defaults are fail-safe.

- [ ] **Step 7: Commit**

```bash
git add apps/api apps/cli tests/security/test_api_approvals.py tests/unit/cli/test_intervene.py
git commit -m "feat: add out-of-band install intervention"
```

---

### Task 5: Add the deterministic coding-agent demo and state controller

**Files:**
- Create: `demo/agent/sss_demo_agent/__init__.py`
- Create: `demo/agent/sss_demo_agent/main.py`
- Create: `apps/api/sss_api/services/demo.py`
- Create: `apps/api/sss_api/routes/demo.py`
- Create: `scripts/demo_reset.py`
- Create: `scripts/demo_replay.py`
- Test: `tests/unit/demo/test_agent.py`
- Test: `tests/integration/test_demo_controller.py`

**Interfaces:**
- Consumes: original `pnpm` executable discovery, `ExasolDemoRepository.reset`,
  `replay_global_evidence`, canary count/reset endpoints and the Guard API.
- Produces: `sss-demo-agent`, fixture-scoped reset/replay/status operations and a deterministic
  state machine `ready -> replayed -> registered -> unprotected -> protected_blocked`.

- [ ] **Step 1: Write failing agent test**

Inject a recording process backend. Assert the agent prints that it is a controlled fixture, invokes
exactly `pnpm add @sss-demo/reserved-synthetic@1.0.0`, and never imports or calls SSS API code.

- [ ] **Step 2: Verify red state**

Run:

```bash
uv run pytest tests/unit/demo/test_agent.py -v
```

Expected: import failure for `sss_demo_agent`.

- [ ] **Step 3: Implement the deterministic agent**

Use short agent-style status lines followed by a single subprocess call with `shell=False`. Propagate
the shim exit code so the terminal visibly proves the block.

- [ ] **Step 4: Write failing state-controller tests**

Assert every action is idempotent, actions cannot run out of order, reset clears only fixture state,
and protected completion requires `package_manager_started=false` plus unchanged total canary count.

- [ ] **Step 5: Implement controller and routes**

Expose reset, replay, register, run-unprotected, run-protected and status as authenticated local-demo
operations. Return specific conflict responses for out-of-order actions.

- [ ] **Step 6: Verify green state**

Run:

```bash
uv run pytest tests/unit/demo/test_agent.py tests/integration/test_demo_controller.py -v
uv run mypy demo/agent apps/api
uv run ruff check demo/agent apps/api tests/unit/demo tests/integration/test_demo_controller.py
```

Expected: agent invokes the real command boundary once; controller enforces the exact sequence.

- [ ] **Step 7: Commit**

```bash
git add demo/agent apps/api scripts tests/unit/demo tests/integration/test_demo_controller.py pyproject.toml uv.lock
git commit -m "feat: add deterministic coding-agent attack demo"
```

---

### Task 6: Build the zero-cost protected demo profile

**Files:**
- Modify: `infra/docker/agent.Dockerfile`
- Create: `infra/docker/demo.compose.yaml`
- Create: `infra/docker/npm-registry/config.yaml`
- Create: `scripts/generate_demo_tls.sh`
- Create: `demo/synthetic-package/package.json`
- Create: `demo/synthetic-package/install.mjs`
- Create: `scripts/demo.sh`
- Test: `tests/security/test_demo_compose.py`
- Test: `tests/e2e/test_agent_guard_demo.py`

**Interfaces:**
- Consumes: API, CLI shims, demo agent, Exasol, local registry and canary.
- Produces: `docker compose -f infra/docker/demo.compose.yaml` profile and one-command terminal demo.

- [ ] **Step 1: Write failing Compose security tests**

Assert agent is non-root, read-only, cap-drop all, no Docker socket, internal-only network, shim path
before real executables, npm registry set to the logical HTTPS origin, and no signing/Exasol/admin
credentials in its environment.

- [ ] **Step 2: Verify red state**

Run:

```bash
uv run pytest tests/security/test_demo_compose.py -v
```

Expected: missing demo Compose file.

- [ ] **Step 3: Implement local TLS registry and synthetic package**

Use a local npm-compatible registry behind a localhost-only TLS reverse proxy. Generate a
short-lived self-signed certificate for `npm.demo.sss.test` into ignored `.runtime/tls` state; do
not commit a private key. Configure containers to trust that certificate. The package install script sends only
`DEMO_ONLY_NOT_A_SECRET` to the canary URL and exits nonzero on any unexpected destination.

- [ ] **Step 4: Build the protected agent image**

Install the SSS CLI, demo agent and shims; retain immutable paths to real package managers; configure
the protected registry and API URLs; run as UID/GID 65532 with only the project volume writable.

- [ ] **Step 5: Write the live E2E test**

From reset, replay evidence, publish the package, run one unprotected install, then run the protected
agent. Assert recurrence tuple, `100/95/75`, one canary event total, one blocked attempt, zero
protected child starts, exit `23`, live `install.blocked` event and retained historical absence.

- [ ] **Step 6: Run live verification**

Run:

```bash
SSS_RUN_DOCKER_TESTS=true uv run pytest tests/e2e/test_agent_guard_demo.py -v
```

Expected: complete local story passes and Compose cleanup leaves no demo containers running.

- [ ] **Step 7: Commit**

```bash
git add infra/docker demo/synthetic-package scripts/demo.sh tests/security/test_demo_compose.py tests/e2e/test_agent_guard_demo.py
git commit -m "feat: run the agent guard demo in a protected workspace"
```

---

### Task 7: Reconcile the optional frontend and final evidence

**Files:**
- Restore: frontend changes from commit `8d2c28e`
- Modify: `apps/web/src/runtime/config.ts`
- Modify: `apps/web/src/api/control-room.ts`
- Modify: `apps/web/src/api/events.ts`
- Modify: `apps/web/src/api/prototype-control-room.ts`
- Modify: `apps/web/src/pages/demo-page.tsx`
- Modify: `docs/measurements/holdout-v1.json`
- Create: `README.md`
- Create: `docs/operations/agent-demo.md`
- Test: `apps/web/src/api/control-room.test.ts`
- Test: `apps/web/src/api/events.test.ts`

**Interfaces:**
- Consumes: live `/v1` API and terminal-first demo state.
- Produces: optional evidence UI with frozen values and documented terminal rehearsal.

- [ ] **Step 1: Restore UI commit and resolve package metadata**

Cherry-pick `8d2c28e`, keep integrated root package/lock decisions, and retain the existing visual
implementation without making it the primary demo surface.

- [ ] **Step 2: Write failing live-contract tests**

Assert prototype mode defaults false, all paths use `/v1`, identity is the frozen scoped package,
absence is 100, policy is `sss-hackathon-v3`, registration age is 43, and event authentication uses
the implemented browser-safe mechanism.

- [ ] **Step 3: Update UI contracts and demo copy**

Label the dashboard optional, add a prominent `Agent protection active` entry point, show that the
operator intervention is handled through `sss intervene`, and remove any simulated success claim
when live mode is selected.

- [ ] **Step 4: Record runtime measurements**

Populate Guard p50/p95 and non-execution only from the live E2E output. Do not alter the pending
Teammate 2 overlap labels unless actual labels have been supplied.

- [ ] **Step 5: Run release verification twice**

Run:

```bash
uv run pytest -q
uv run mypy packages/core apps
uv run ruff check .
pnpm test
pnpm typecheck
pnpm web:build
git diff --check
SSS_RUN_DOCKER_TESTS=true uv run pytest tests/e2e/test_agent_guard_demo.py -v
SSS_RUN_DOCKER_TESTS=true uv run pytest tests/e2e/test_agent_guard_demo.py -v
```

Expected: all checks pass; both demo runs end with canary one and protected child starts zero.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: finalize terminal-first agent guard demonstration"
```
