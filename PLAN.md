# SSS — Stop Slop Squatting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Build a deployable seven-day security product that maintains global PyPI/npm hallucination intelligence and autonomously blocks risky package installs by coding agents.

**Architecture:** Scheduled collectors create provenance-preserving registry and recommendation evidence in Exasol. A deterministic policy service combines historical absence, global recurrence, later registration, source, and artifact evidence. `sss protect` runs agents in a Docker boundary where command shims and a policy-aware registry gateway enforce decisions independently of MCP.

**Tech Stack:** Python 3.12, FastAPI, Typer, Exasol Personal, React 19, TypeScript, Vite, D3, Docker Compose, PyPI/npm APIs, GitHub REST API, pytest, Vitest, Playwright.

**Spec:** `outputs/ARCHITECTURE.md`  
**Stack detail:** `outputs/TECH_STACK.md`  
**Demo/team contract:** `outputs/FINAL_DEMO_AND_TEAM_SPLIT.md`

## Global constraints

- MVP ecosystems are exactly PyPI and npm.
- Supported clients: pip, uv, Poetry manifests, npm, pnpm, Yarn, and npx.
- Policy version is `sss-hackathon-v3`.
- Only attributable model evidence plus conclusive registry absence earns `VERIFIED_HALLUCINATION`.
- `404` from an approved package-metadata endpoint is the only live absence result.
- `401`, `403`, `429`, `5xx`, timeout, DNS, TLS, and malformed responses remain `UNKNOWN`.
- Historical absence evidence is immutable; later registration creates a transition.
- The three indices are not probabilities and must remain separately labelled.
- Raw unregistered names are private threat intelligence; public views show aggregates and synthetic names only.
- Client telemetry is opt-in and never contains prompts, code, environment variables, usernames, paths, or repository names.
- `REVIEW` defaults to block for non-interactive agents.
- Blocked commands never start the real package manager.
- Production scanners never dynamically execute unknown public artifacts.
- All subprocesses receive argument vectors and use `shell=False`.
- The strongest enforcement guarantee is limited to an unprivileged SSS-protected Docker workspace.

---

## 1. Team ownership

### Teammate 1 — Intelligence and policy engineer

Owns:

- Domain types, normalization, extraction, aliases, and evidence state machine.
- PyPI/npm registry clients and PyPI baseline builder.
- Controlled model probes, public-source collector, and transition scheduler.
- Exasol migrations, repositories, analytical views, indices, and policy engine.
- Intelligence correctness, measurement, and judge answers about detection.

Primary directories: `packages/core`, `apps/worker`, `infra/exasol`, policy portions of `apps/api`.

### Teammate 2 — Enforcement and product engineer

Owns:

- FastAPI composition, authentication, REST/SSE routes, and OpenAPI contract.
- `sss` CLI, command adapters, shims, protected launcher, approval grants.
- Registry gateway, Docker isolation, local registries, canary, deployment.
- React application implementation and integration of approved Figma work.
- Reliability, end-to-end tests, and judge answers about enforcement/deployment.

Primary directories: `apps/api`, `apps/cli`, `apps/gateway`, `apps/web`, `demo`, `infra/docker`.

### Teammate 3 — Product and visual designer

Owns:

- SSS/“Triple-S” identity, logo, typography, color/accessibility tokens, and Figma library.
- Information architecture and high-fidelity Radar, evidence, alert, approval, and demo screens.
- Motion specification, responsive states, empty/loading/error states, and redaction UX.
- Developer-ready measurements, assets, copy deck, and interaction annotations.
- Pitch deck, demo narration, video framing, submission graphics, and final visual QA.

Primary artifacts: Figma, `docs/design`, `apps/web/src/styles/tokens.css`, exported SVG assets, pitch/demo assets. The designer does not own backend implementation.

### Integration rule

Each engineer may work with Codex in a separate task, but both must read the same architecture, stack, API contract, and demo fixture. Interface changes require a short written update in `docs/contracts/CHANGELOG.md`. The designer approves visible states and copy; Teammate 1 approves evidence semantics; Teammate 2 approves executable/deployment changes.

---

## 2. Repository map

```text
sss/
├── apps/
│   ├── api/sss_api/
│   │   ├── main.py
│   │   ├── dependencies.py
│   │   ├── schemas/
│   │   └── routes/{health,observations,registry,radar,guard,approvals,events}.py
│   ├── worker/sss_worker/
│   │   ├── scheduler.py
│   │   ├── jobs/{probe,github,baseline,recheck,inspect}.py
│   │   └── providers/{base,replay}.py
│   ├── cli/sss_cli/
│   │   ├── main.py
│   │   ├── protect.py
│   │   ├── guard.py
│   │   ├── approvals.py
│   │   └── adapters/{pip,uv,npm,pnpm,yarn,npx}.py
│   ├── gateway/sss_gateway/{main,pypi,npm,artifacts}.py
│   └── web/src/
│       ├── routes/{Radar,PackageDetail,DecisionCenter,Coverage,Demo}.tsx
│       ├── components/
│       ├── api/
│       └── styles/tokens.css
├── packages/core/sss_core/
│   ├── domain.py
│   ├── identity.py
│   ├── extraction/{python,npm,shell}.py
│   ├── registries/{base,pypi,npm}.py
│   ├── evidence/{state,scoring,attestation}.py
│   ├── policy/{engine,reasons,approvals}.py
│   ├── privacy/redaction.py
│   └── repositories/{base,exasol}.py
├── helpers/npm-spec-parser/
├── infra/exasol/{migrations,views,udfs}/
├── infra/docker/
├── demo/{fixtures,scripts,synthetic-package}/
├── docs/{contracts,design,operations}/
├── tests/{unit,integration,e2e,security}/
├── docker-compose.yml
├── pyproject.toml
├── pnpm-workspace.yaml
└── .env.example
```

---

## 3. Seven-day milestone map

| Day | Required exit gate |
|---|---|
| 1 | Monorepo builds; domain/identity tests pass; Figma direction and five screen wireframes approved |
| 2 | Exasol schema works; PyPI/npm truth tables pass; Radar high-fidelity design approved |
| 3 | Replay probe, public-source fixture, recurrence, and transition views produce fixed demo values |
| 4 | Guard blocks pip and pnpm without spawning; API/SSE and core UI read real Exasol data |
| 5 | Protected Docker path, gateway, local registration, and safe canary scenario pass end-to-end |
| 6 | Full visual polish, security tests, measurements, cloud/local deployment, and pitch deck complete |
| 7 | Freeze features; rehearse, record fallback video, fix only severity-one failures, submit |

Cut order if behind: MCP first, live provider adapter second, Yarn/npx edge cases third. Never cut the registration transition, npm+PyPI registry checks, Exasol analytics, protected pnpm block, or evidence UI.

---

### Task 1: Bootstrap contracts and cross-ecosystem domain

**Owner:** Teammate 1; Teammate 2 reviews public interfaces.  
**Files:** Create `pyproject.toml`, `package.json`, `pnpm-workspace.yaml`, `.env.example`, `packages/core/sss_core/domain.py`, `packages/core/sss_core/identity.py`, `tests/unit/test_identity.py`, `docs/contracts/openapi-decisions.md`.

**Produces:** `Ecosystem`, `PackageIdentity`, `RegistryStatus`, `CandidateStatus`, `EvidenceProvenance`, `InstallRequest`, `EvidenceScores`, `PolicyDecision`, `canonicalize_identity()`.

- [ ] Write failing tests for `Django_REST.Framework → django-rest-framework`, `@Scope/Thing → @scope/thing`, and identical names remaining distinct across ecosystems.
- [ ] Run `uv run pytest tests/unit/test_identity.py -v`; expect failures because types/functions do not exist.
- [ ] Implement the exact enums/dataclasses from Architecture §11 and `canonicalize_identity(ecosystem, origin, name) -> PackageIdentity`.
- [ ] Add strict validation for npm scope/name syntax and approved `https` registry origins; reject embedded credentials and fragments.
- [ ] Run unit tests, `uv run mypy --strict packages/core`, and `uv run ruff check .`.
- [ ] Freeze the request/decision JSON examples in `docs/contracts/openapi-decisions.md`.
- [ ] Commit: `feat: define sss package and policy contracts`.

### Task 2: Build safe extractors and command adapters

**Owner:** Teammate 1 owns extraction; Teammate 2 owns CLI adapters.  
**Files:** Create `packages/core/sss_core/extraction/*.py`, `helpers/npm-spec-parser/`, `apps/cli/sss_cli/adapters/*.py`, `tests/unit/test_python_extraction.py`, `tests/unit/test_npm_extraction.py`, `tests/security/test_command_parsing.py`, `data/import_aliases.json`, `data/stdlib_manifest.json`.

**Consumes:** `PackageIdentity`.  
**Produces:** `ExtractedPackage`, `extract_python_mentions(text)`, `extract_npm_mentions(text)`, `parse_install_argv(argv) -> tuple[InstallRequest, ...]`.

- [ ] Add failing fixtures for pip/uv/requirements/pyproject and npm/pnpm/Yarn/npx/package manifests, including scoped packages and aliases.
- [ ] Add hostile cases containing `;`, `&&`, pipes, redirects, `$()`, backticks, direct Git URLs, paths, and alternate registries; expected result is rejection or explicit source classification, never evaluation.
- [ ] Implement PyPI parsing with `packaging`, AST, `tomllib`, stdlib exclusion, and the versioned alias table.
- [ ] Implement the line-delimited Node helper with `npm-package-arg`; assert it returns classification only and has no install capability.
- [ ] Implement adapters that expand direct manifest requirements while preserving version, source, and direct/transitive context.
- [ ] Use Hypothesis to fuzz canonical package names and argv boundaries.
- [ ] Run `uv run pytest tests/unit/test_*extraction.py tests/security/test_command_parsing.py -v` and helper tests.
- [ ] Commit: `feat: parse pypi and npm install intent safely`.

### Task 3: Create Exasol schema, repositories, and views

**Owner:** Teammate 1.  
**Files:** Create ordered migrations in `infra/exasol/migrations/`, views in `infra/exasol/views/`, UDF in `infra/exasol/udfs/package_name_similarity.py`, repository files, `tests/integration/test_exasol_schema.py`, `tests/integration/test_exasol_views.py`.

**Produces:** `EvidenceRepository`, `RadarRepository`, `PolicyRepository`, and every table/view in Architecture §12.

- [ ] Write an integration test that migrates an empty schema twice and expects the second run to be a no-op.
- [ ] Add a fixture with two ecosystems, three model configurations, 46 verified recommendations, eight client attempts, five public failed references, 11 observation days, multiple unknown checks, and one later registration.
- [ ] Write failing SQL assertions for `V_VERIFIED_HALLUCINATIONS`, `V_GLOBAL_RECURRENCE`, `V_REGISTRATION_TRANSITIONS`, private Radar, and redacted public aggregates.
- [ ] Implement parameterized repositories and atomic evidence/transition writes.
- [ ] Implement the similarity UDF and test canonical-name edge cases.
- [ ] Prove public aggregate rows never expose an absent package name.
- [ ] Run `uv run pytest tests/integration/test_exasol_schema.py tests/integration/test_exasol_views.py -v`.
- [ ] Commit: `feat: persist global slopsquatting evidence in exasol`.

### Task 4: Implement registry oracles and immutable transitions

**Owner:** Teammate 1.  
**Files:** Create `registries/base.py`, `registries/pypi.py`, `registries/npm.py`, `apps/worker/sss_worker/jobs/baseline.py`, `jobs/recheck.py`, `tests/unit/test_registry_truth_table.py`, `tests/integration/test_registration_transition.py`.

**Produces:** `RegistryOracle.check(identity) -> RegistryEvidence`, `BaselineBuilder.build()`, `TransitionDetector.detect(identity) -> CandidateStatus`.

- [ ] Write `respx` truth-table tests for `200`, `404`, `401`, `403`, `429`, `5xx`, timeout, TLS failure, and malformed bodies for both registries.
- [ ] Assert only approved-endpoint `404` returns `ABSENT`; all failures return a typed `UNKNOWN_*`.
- [ ] Build a reproducible PyPI baseline fixture twice and assert identical sorted bytes and SHA-256.
- [ ] Test scoped npm URL encoding and alternate-registry identity separation.
- [ ] Test `404 at T0 → 200/release at T1` creates a transition while preserving the T0 row/hash.
- [ ] Implement bounded retry only for safe reads, maximum three attempts with jitter disabled in tests.
- [ ] Run registry and transition tests.
- [ ] Commit: `feat: detect immutable absence to registration transitions`.

### Task 5: Build continuously updated intelligence collectors

**Owner:** Teammate 1.  
**Files:** Create `apps/worker/sss_worker/providers/{base,replay}.py`, `jobs/{probe,github,recheck}.py`, `scheduler.py`, `tests/unit/test_probe_collector.py`, `tests/unit/test_github_collector.py`, `tests/unit/test_scheduler.py`, `demo/fixtures/probe_corpus.jsonl`.

**Produces:** idempotent `run_probe_suite`, `scan_public_sources`, `recheck_watchlist`, and persisted job cursors.

- [ ] Define a 48-task prompt manifest split across Python/npm and at least six task categories; store hashes and model configuration.
- [ ] Write a replay test proving duplicate collection produces no duplicate mention or recurrence count.
- [ ] Write GitHub fixture tests for public manifest discovery, conclusive CI failure, rate-limit cursor retention, deletion, and false-positive prose rejection.
- [ ] Implement source provenance so public/client evidence can never be relabelled `MODEL_PROBE`.
- [ ] Implement schedules: high-risk 15 minutes, remaining watchlist six hours, probes daily, public scan hourly, baseline daily.
- [ ] Add per-source deduplication and a cap preventing one client/source from dominating recurrence.
- [ ] Run worker tests and replay the fixture into integration Exasol.
- [ ] Commit: `feat: continuously collect global package intelligence`.

### Task 6: Implement indices, policy, privacy, and approvals

**Owner:** Teammate 1 owns indices/policy; Teammate 2 owns cryptographic approval plumbing.  
**Files:** Create `evidence/{state,scoring,attestation}.py`, `policy/{engine,reasons,approvals}.py`, `privacy/redaction.py`, `tests/unit/test_scoring.py`, `tests/unit/test_policy.py`, `tests/security/test_approvals.py`, `tests/security/test_telemetry_redaction.py`.

**Produces:** `score_target_attractiveness`, `score_package_policy_risk`, `PolicyEngine.assess`, `ApprovalService.issue/consume`, `redact_client_event`.

- [ ] Write exact score tests for the fixed demo: absence `100`, attractiveness `95`, post-registration risk `75`.
- [ ] Add hard-rule tests: absent block, high-attractiveness transition block, unapproved source block, unknown strict-mode block, established approved allow.
- [ ] Assert non-interactive `REVIEW` becomes `BLOCK`.
- [ ] Sign approvals containing exact package, version, registry, artifact hash, project, expiry, nonce, and policy version.
- [ ] Test altered fields, expiry, wrong project, missing hash, and second consumption all fail.
- [ ] Serialize a telemetry fixture containing forbidden keys and prove only the allowlisted schema leaves the process.
- [ ] Attest canonical decision evidence with SHA-256.
- [ ] Run policy/security tests.
- [ ] Commit: `feat: enforce deterministic sss policy and scoped approvals`.

### Task 7: Expose REST, SSE, and optional MCP boundaries

**Owner:** Teammate 2.  
**Files:** Create `apps/api/sss_api/main.py`, schemas/routes listed in repository map, `tests/integration/test_api.py`, `tests/integration/test_sse.py`; create MCP adapter only after the exit gate.

**Consumes:** repositories, policy engine, approval service.  
**Produces:** OpenAPI contract and routes in Architecture §13.

- [ ] Write failing API tests for model/public/client observations, package detail, Radar, check, attempts, approvals, and health.
- [ ] Require authentication, idempotency keys, strict unknown-field rejection, and request-size limits.
- [ ] Make `/health/ready` verify Exasol connectivity, schema version, and `sss-hackathon-v3` policy availability.
- [ ] Implement SSE event IDs for `observation.completed`, `registration.transition`, `install.blocked`, and `approval.consumed`, plus 15-second heartbeat.
- [ ] Assert the public route cannot enumerate private absent names.
- [ ] Generate OpenAPI and have both engineers approve the diff.
- [ ] If core tests are green, expose the four MCP tools as thin API calls; otherwise omit MCP.
- [ ] Commit: `feat: expose sss intelligence and guard api`.

### Task 8: Build autonomous Guard CLI and package-manager shims

**Owner:** Teammate 2.  
**Files:** Create `apps/cli/sss_cli/{main,guard,protect,approvals}.py`, executable shims, `tests/unit/test_guard_cli.py`, `tests/security/test_no_child_process.py`.

**Produces:** `sss check`, `sss guard`, `sss protect`, `sss doctor`, and shims for supported clients.

- [ ] Write a recording runner test where a registered-after-hallucination `pnpm add` decision returns exit `23` and records zero child starts.
- [ ] Repeat for conclusively absent pip install, alternate npm registry, direct URL, VCS, and assessment outage.
- [ ] Test one established approved package starts the immutable real executable exactly once with the original safe argv.
- [ ] Implement terminal output showing agent, command, ecosystem, registry, three indices, reason codes, and “installation was not started.”
- [ ] Implement noninteractive detection; never prompt on stdin when no TTY.
- [ ] Implement `sss protect` session/project identity and controlled environment construction.
- [ ] Ensure the agent never receives an administrative/signing credential.
- [ ] Run CLI and non-execution security tests.
- [ ] Commit: `feat: block autonomous agent installs before execution`.

### Task 9: Implement gateway and protected Docker boundary

**Owner:** Teammate 2.  
**Files:** Create `apps/gateway/sss_gateway/*.py`, `infra/docker/agent.Dockerfile`, Compose network/profile configuration, `tests/integration/test_gateway.py`, `tests/security/test_container_boundary.py`.

**Produces:** minimum npm/PEP 503 proxy paths and isolated protected workspace.

- [ ] Write tests that proxy approved metadata/artifacts and deny unknown origin, direct source, invalid path, oversized body, and blocked policy.
- [ ] Stream artifact bytes while hashing; do not buffer unlimited bodies.
- [ ] Configure pip/npm inside the protected image to use the gateway.
- [ ] Run as unprivileged, set `no-new-privileges`, omit Docker socket, use read-only base, and expose only the project volume.
- [ ] Build a network with access to API/gateway but no route to public registry hosts from the agent container.
- [ ] Prove direct `curl` to the public registry fails while a permitted package resolves through the gateway.
- [ ] Prove a blocked transitive package never reaches artifact download.
- [ ] Commit: `feat: enforce registry policy in protected workspace`.

### Task 10: Build Radar from the approved Figma system

**Owner:** Teammate 3 designs; Teammate 2 implements.  
**Files:** Create Figma library and `docs/design/*`; implement `apps/web/src` routes/components/styles; add component and accessibility tests.

**Produces:** real-data Radar, package detail, decision center, coverage, and guided demo.

- [ ] Designer delivers low-fidelity information architecture for all five routes and obtains team approval before high fidelity.
- [ ] Designer defines semantic tokens for background, surface, text, verified absence, transition, blocked, review, and allowed states with WCAG AA contrast.
- [ ] Designer supplies desktop plus narrow-screen frames, loading/empty/error/stale/redacted states, focus order, and motion timing.
- [ ] Engineer implements typed API client and `EventSource` reconnection with last event ID.
- [ ] Implement D3 recurrence constellation where radius means attractiveness and color means candidate state; never render private names in public mode.
- [ ] Implement temporal evidence timeline with provenance badges and immutable absence → registration → attempt ordering.
- [ ] Implement decision drawer and exact-scope approval dialog; avoid a generic permanent-trust action.
- [ ] Run Vitest, `tsc --noEmit`, build, keyboard testing, reduced-motion check, and Playwright screenshots.
- [ ] Designer performs visual QA at 1440×900 and 390×844; record issues with screenshot and component name.
- [ ] Commit: `feat: visualize global slopsquatting evidence and blocks`.

### Task 11: Create safe dual-ecosystem demo lab

**Owner:** Teammate 2; Teammate 1 verifies evidence semantics; Teammate 3 controls visible story.  
**Files:** Create `demo/synthetic-package/`, local registries, canary, replay/reset/register/attack scripts, demo Compose profile, `tests/e2e/test_demo_story.py`.

**Produces:** deterministic replay, local registration, unprotected canary, and protected autonomous block.

- [ ] Reserve and validate a synthetic demo name; label every replayed/global observation synthetic.
- [ ] Create a harmless npm fixture whose install lifecycle makes one request containing `DEMO_ONLY_NOT_A_SECRET` to the local canary and performs no other sensitive action.
- [ ] Make reset idempotently produce zero registrations, attempts, approvals, and canary events.
- [ ] Replay the fixed 46/3/8/11 evidence values through production ingestion interfaces.
- [ ] Register the fixture locally and run the same transition detector as production.
- [ ] In a disposable unprotected victim, install once and assert exactly one canary event.
- [ ] Launch a noninteractive fake/Codex-shaped agent through `sss protect`; attempt `pnpm add`; assert decision `BLOCK`, child not started, and canary still one.
- [ ] Show the SSE block event and ordered Exasol evidence in Radar.
- [ ] Run the whole story twice from reset and compare expected state.
- [ ] Commit: `feat: demonstrate autonomous slopsquatting prevention safely`.

### Task 12: Measurement, security review, deployment, and submission

**Owners:** All three in their lanes.  
**Files:** Create holdout dataset, measurement scripts, operations docs, README, pitch deck, narration, screenshots, and fallback recording.

- [ ] Teammates 1 and 2 independently label 50 overlapping examples in a holdout of at least 200 cross-ecosystem mentions; resolve disagreements and freeze the dataset hash.
- [ ] Report extraction precision/recall, micro/macro hallucination rate, unknown rate, public-signal precision, transition delay, Guard p50/p95, and non-execution invariant.
- [ ] Run `ruff`, strict mypy, pytest, frontend lint/type/test/build, Playwright, dependency audits, secret scan, image scan, and `git diff --check` where Git exists.
- [ ] Deploy the core Compose profile locally and on the chosen AWS/Azure host; verify TLS, health, persistence, reset, and demo from a clean browser.
- [ ] Designer finishes a concise pitch deck: problem, temporal insight, global network, autonomous enforcement, Exasol value, demo proof, deployment, future.
- [ ] Record a two-to-three-minute fallback video with readable terminal/UI text and no real secrets or public target names.
- [ ] Freeze fixture values, copy, policy version, container digests, and demo order.
- [ ] Commit/tag the final submission only after the full rehearsal passes twice.

---

## 4. Daily work division

| Day | Teammate 1 — Intelligence | Teammate 2 — Enforcement | Teammate 3 — Design |
|---|---|---|---|
| 1 | Domain, identity, Python extraction | Repo/API shell, npm parser helper | Brand directions, IA, low-fi screens |
| 2 | Exasol, PyPI/npm clients | CLI contracts, API wiring | Final visual direction, tokens, hi-fi Radar |
| 3 | Collectors, recurrence, transitions | Guard engine integration, SSE | Package timeline, decision/approval states |
| 4 | Policy, scores, fixtures | Shims, React integration | Demo control room, motion, responsive states |
| 5 | Evidence validation, measurements | Gateway, Docker boundary, demo lab | Visual QA, pitch structure, submission assets |
| 6 | Security/data review, judge prep | E2E, deployment, performance | Final polish, deck, recording direction |
| 7 | Rehearse and fix data blockers | Rehearse and fix runtime blockers | Rehearse, record, submission visual checks |

## 5. Merge and communication discipline

- Daily 15-minute contract sync at the start and one integration build before stopping.
- Teammate 1 publishes domain/OpenAPI-affecting changes before Teammate 2 consumes them.
- Teammate 3 never hands off screens without loading/error/empty/redacted states and exact copy.
- Teammate 2 never invents evidence labels in the UI; use API enums and designer-approved copy.
- Feature branches remain small; rebase/merge only after their focused tests pass.
- No direct edits to another owner’s primary directory without a message and review.
- A failing main integration build stops new feature work.

## 6. Final definition of done

- [ ] PyPI and npm package identity/extraction pass the labelled holdout.
- [ ] Controlled probe, public, and client evidence remain visibly separated.
- [ ] Conclusive absence and unknown network states cannot be confused.
- [ ] The fixed synthetic package reaches the exact 100/95/75 indices.
- [ ] The registration transition retains proof of earlier absence.
- [ ] Public endpoints reveal no raw absent target names.
- [ ] Opt-in telemetry contains no forbidden content.
- [ ] Autonomous protected pnpm installation is blocked without MCP or agent response.
- [ ] Blocked path never starts a package manager or adds a canary event.
- [ ] Exact-scope approval cannot be replayed or widened.
- [ ] Radar reads real Exasol views and receives live block events.
- [ ] Clean Compose deployment and reset are documented and reproducible.
- [ ] Figma, implementation, screenshots, pitch, narration, and fixture values agree.
- [ ] Two complete rehearsals pass from clean reset.

## 7. Execution handoff

Use two Codex implementation tasks in parallel only after Task 1 freezes shared interfaces:

1. **Intelligence lane:** Teammate 1 executes Tasks 2–6 in the core/worker/Exasol areas.
2. **Enforcement lane:** Teammate 2 executes Tasks 7–9 against frozen contracts, then integrates Task 10 and owns Task 11.
3. **Design lane:** Teammate 3 works from the same demo contract and delivers implementation-ready Figma checkpoints daily.

Task 12 is a whole-team gate. Do not split final evidence, demo values, and product claims across inconsistent versions.
