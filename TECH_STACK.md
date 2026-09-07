# SSS — Stop Slop Squatting: Technology Stack

**Target:** A deployable two-ecosystem security MVP in seven days.  
**Principle:** deterministic parsing and policy, immutable temporal evidence, private threat intelligence, and enforcement before package execution.

## 1. Stack at a glance

```text
React + TypeScript Radar
          │ REST + SSE
FastAPI intelligence/policy API ───── Exasol Personal
          │                                  ▲
          ├── scheduled workers ─────────────┤
          ├── npm + PyPI registry clients ───┤
          └── SSS Guard / registry gateway ──┘
                           │
                    sss protect CLI
                           │
             protected Docker agent workspace
```

## 2. Version and dependency policy

- Python: `>=3.12,<3.13`.
- Node.js: active LTS supported by the chosen deployment image.
- Package manager for repository JavaScript: `pnpm` with committed `pnpm-lock.yaml`.
- Python dependency manager: `uv` with committed `uv.lock`.
- Frontend packages use bounded major ranges during development; lockfiles are deployment truth.
- Production builds use frozen lockfiles and fail if resolution would modify them.
- Pin Docker image digests for the final demo rehearsal.

## 3. Backend runtime

| Technology | Role |
|---|---|
| Python 3.12 | API, workers, Guard, gateway, collectors, policy engine |
| FastAPI | Typed REST API and Server-Sent Events |
| Uvicorn | ASGI runtime |
| Pydantic v2 | Boundary validation and canonical evidence DTOs |
| Typer | `sss` command-line application |
| Rich | Clear terminal decisions and evidence tables |
| `pyexasol` | Exasol SQL, transactions, bulk inserts, and health checks |
| `httpx` | Async registry/provider/GitHub requests and proxy streaming |
| `tenacity` | Bounded retry for explicitly retryable reads |
| `APScheduler` | In-process schedule definition for the worker container |
| `structlog` | Structured logs with request/job/decision IDs |
| `cryptography` | Signed approval grants and signed cached policy feed |

No Celery, Redis, Kafka, vector database, or agent framework is required for the MVP. Scheduled jobs are idempotent Exasol-backed operations run by one worker container.

## 4. Package parsing

### 4.1 Shared identity

| Library/tool | Purpose |
|---|---|
| `packageurl-python` | Portable `pkg:pypi/...` and `pkg:npm/...` identities |
| `urllib.parse` | Normalize and validate registry origins and direct URLs |
| `bashlex` | Reject unsafe shell syntax without executing it |

### 4.2 Python/PyPI

| Library | Purpose |
|---|---|
| `packaging` | PEP 440 versions, PEP 508 requirements, canonical names |
| Python `ast` | Extract imports from generated Python code |
| Python `tomllib` | Parse `pyproject.toml` and Poetry sections |
| `stdlib-list` | Version-matched standard-library exclusion |

A versioned local alias table resolves high-confidence import/distribution differences. Unresolved imports stay ambiguous and cannot become verified hallucinations.

### 4.3 npm ecosystem

| Library/tool | Purpose |
|---|---|
| Python `json` | `package.json` and `package-lock.json` |
| `PyYAML` with safe loading | `pnpm-lock.yaml` fixtures and direct dependency fields |
| Small Node helper using `npm-package-arg` | Correct parsing of scoped names, versions, tags, aliases, URLs, Git, and paths |

The helper accepts and returns line-delimited JSON. It never installs or executes a requested package. Yarn lock parsing is limited to entries corresponding to direct manifest dependencies in the MVP.

## 5. Registry evidence

### 5.1 PyPI

- PyPI Simple JSON Index for daily baselines.
- Project-level Simple or JSON endpoint for live checks.
- PEP 503 canonicalization.
- Preserve `_last-serial`, `ETag`, response time, endpoint, and evidence SHA-256 where available.

### 5.2 npm

- Configured npm registry metadata endpoint for exact package checks.
- Correct percent-encoding of scoped names.
- Preserve registry origin, HTTP status, selected cache headers, response time, and evidence hash.
- `404` is absence only from the approved metadata endpoint.

### 5.3 Truth table

| Result | Stored state |
|---|---|
| Valid package metadata (`200`) | `REGISTERED` |
| Conclusive endpoint `404` | `ABSENT` |
| `401`/`403` | `UNKNOWN_AUTH` |
| `429` | `UNKNOWN_RATE_LIMIT` |
| `5xx` | `UNKNOWN_SERVER` |
| DNS/TLS/timeout | `UNKNOWN_NETWORK` |
| Invalid/malformed response | `UNKNOWN_RESPONSE` |

Only `ABSENT` may create historical absence evidence.

## 6. Global intelligence collectors

### 6.1 Model probe worker

- Provider adapters behind an internal `ModelProvider` protocol.
- Secrets passed through environment/secret store, never persisted.
- Raw prompts/responses use explicit retention classes; hashes are always stored.
- Deterministic replay adapter is mandatory for tests and demo.
- Avoid a multi-provider abstraction library in week one; implement only the provider credentials the team actually has.

### 6.2 Public GitHub worker

- GitHub REST Search API with an authenticated token.
- Cursor/checkpoint persisted in Exasol.
- Scan public manifests, lockfiles, explicit install commands, and conclusive resolution-failure excerpts.
- Respect API quotas, repository visibility, deletion, and terms.
- Store public URL hash and minimal excerpt hash; do not mirror repositories.

GitHub results are discovery evidence, not proof of model hallucination.

### 6.3 Opt-in client telemetry

- HTTPS JSON events with schema version and idempotency key.
- Rotating client pseudonym generated locally.
- Redaction allowlist: only explicitly defined fields are serialized.
- No prompt, code, environment, username, repository name, or absolute path.
- Telemetry is off by default for individual installations; enabled explicitly for the demo organization.

## 7. Exasol

### 7.1 Responsibilities

- Immutable observations and registry evidence.
- Global recurrence and model-package hallucination rate.
- Absent-to-registered temporal joins.
- Private watchlist prioritization.
- Policy evidence lookup and decision audit.
- Public aggregate views with disclosure controls.
- Demo and benchmark queries.

### 7.2 Access pattern

- Repository classes own parameterized SQL.
- Workers batch insert mentions/checks.
- One transaction stores registry evidence, state transition, decision, and evidence attestation where applicable.
- Migrations are ordered SQL files with a `SCHEMA_MIGRATIONS` ledger.
- API uses a bounded connection pool and health/readiness probes.

### 7.3 Exasol-specific showcase

Implement a Python scalar UDF `PACKAGE_NAME_SIMILARITY` for normalized edit similarity to established packages. It is an explanatory feature, not the defining slopsquatting signal.

## 8. Deterministic policy engine

- Pure Python functions over immutable Pydantic/domain objects.
- Policy identifier `sss-hackathon-v3` included in every decision.
- Separate `absence_confidence`, `target_attractiveness`, and `package_policy_risk`.
- Reason codes are stable machine-readable enums.
- Hard rules override score bands.
- No LLM or ML classifier decides execution.
- Canonical evidence JSON is SHA-256 attested.

## 9. SSS Guard and command adapters

### 9.1 CLI

```text
sss protect -- codex
sss protect -- claude
sss check <package> --ecosystem pypi|npm
sss guard -- <package-manager argv...>
sss radar open
sss doctor
```

### 9.2 Supported direct commands

- `pip install`, `pip3 install`, `python -m pip install`.
- `uv add` and `uv pip install`.
- `npm install`/`npm i`, `pnpm add`, `yarn add`, and `npx`.
- Requirements/manifests referenced by supported commands are expanded before approval.

### 9.3 Subprocess guarantees

- Accept `list[str]`, never a shell command string.
- Reject shell metacharacters and unsupported subcommands.
- Resolve real package-manager executable from an SSS-owned immutable map, not untrusted `PATH` after approval.
- Execute with `shell=False`, a minimal environment, and explicit working directory.
- Record `child_started=false` before returning every block.
- Exit code `23`: policy block; `24`: assessment unavailable/invalid request.

## 10. Registry gateway and protected workspace

### 10.1 Gateway

FastAPI/Starlette streaming routes implement the minimum read paths required by:

- PEP 503/691 Simple project metadata and approved artifacts.
- npm package metadata and approved tarball forwarding.

The gateway does not terminate arbitrary HTTPS traffic. The protected package managers are configured to use its HTTP(S) endpoint. Artifact bytes are streamed while hashing and enforcing size limits.

### 10.2 Workspace isolation

- Docker Engine and Compose for the MVP security boundary.
- Unprivileged user, read-only base filesystem, explicit writable project volume.
- No Docker socket inside the protected agent container.
- Network attached only to SSS gateway/API; public registry hosts are not directly routable.
- Resource limits and `no-new-privileges`.
- Agent process receives no SSS administrative credential.

## 11. Artifact inspection

| Technology | Purpose |
|---|---|
| `zipfile`, `tarfile` | Bounded archive inspection after manual path validation |
| Python `ast` | Static Python build/setup rules |
| `esprima` or a small Node AST helper | Static npm lifecycle-script source rules |
| `hashlib` | Streaming SHA-256 |

Limits:

- 20 MiB compressed.
- 100 MiB expanded.
- 10,000 entries.
- 5 MiB per file.
- Reject traversal, absolute paths, links/devices, and extreme compression ratios.

Unknown public packages are never dynamically executed by the scanner.

## 12. API

- FastAPI route modules for observations, registry checks, Radar, packages, Guard, attempts, approvals, and SSE.
- OpenAPI is the contract between CLI and web.
- Request body limit and strict unknown-field rejection.
- Idempotency key required for writes.
- Service authentication for workers; session authentication for UI; short-lived Guard session token.
- `/health/live` checks process health; `/health/ready` checks Exasol, policy, and migration version.

## 13. Frontend

| Technology | Role |
|---|---|
| React 19 + TypeScript | Application UI |
| Vite | Development and production build |
| React Router | Radar/detail/decisions/settings/demo routes |
| Tailwind CSS v4 | Token-based styling |
| D3 | Recurrence constellation and temporal evidence timeline |
| Native `EventSource` | Transition and Guard notifications |
| Vitest + Testing Library | Component tests |
| Playwright | Browser end-to-end story |

Avoid Redux, Axios, a second charting library, and a component megaframework. Use typed `fetch`, route-local state, reusable accessible primitives, and CSS/SVG transitions.

Primary screens:

1. Live private Radar.
2. Package evidence timeline.
3. Installation decision drawer.
4. Exact-scope approval dialog.
5. Global source/registry coverage.
6. Guided demo control room.

## 14. Optional MCP server

Use the maintained Python MCP SDK only after core Guard enforcement passes. The server is a thin adapter over existing API methods and exposes no raw global watchlist enumeration.

Tools:

- `sss.check_package`
- `sss.explain_decision`
- `sss.find_safe_alternatives`
- `sss.report_suspected_hallucination`

MCP failure never disables Guard.

## 15. Testing

| Tool | Scope |
|---|---|
| `pytest` | Backend, collectors, Guard, gateway, policy |
| `pytest-asyncio` | Async API/client tests |
| Hypothesis | Package names, scoped names, versions, and command vectors |
| `respx` | PyPI/npm/GitHub/provider HTTP truth tables |
| Testcontainers or Compose profiles | Exasol/local registries integration |
| Vitest + Testing Library | UI components and states |
| Playwright | Full browser demo and approval flow |
| `ruff` | Python format/lint |
| `mypy --strict` | Python type checking |
| ESLint + `tsc --noEmit` | TypeScript checks |
| `pip-audit` and `pnpm audit` | Dependency audit before submission |

Security tests must assert non-execution, telemetry redaction, approval scope, source validation, archive safety, and fail-closed behavior.

## 16. Deployment and operations

### 16.1 Compose profiles

- `core`: Exasol, API, worker, web, gateway.
- `demo`: core plus Verdaccio-compatible local npm registry, local PyPI index, canary, protected/unprotected victims.
- `test`: deterministic fakes and integration runners.

### 16.2 Cloud

- One Linux VM is enough for judging.
- Caddy or Nginx terminates TLS and routes UI/API/gateway hosts.
- AWS/Azure secret store provides tokens.
- Persistent volumes retain Exasol and demo state.
- Nightly encrypted export of schema and evidence fixtures.

### 16.3 Observability

- Structured JSON logs keyed by request, job, package identity, and decision ID.
- Metrics: job lag, quota remaining, registry latency, unknown rate, transition delay, Guard latency, decisions, SSE connections.
- Radar includes data-as-of time and collector health.
- No sensitive package names in default application logs.

## 17. Environment configuration

```text
SSS_ENV
SSS_POLICY_VERSION=sss-hackathon-v3
SSS_PUBLIC_BASE_URL
SSS_EXASOL_DSN
SSS_EXASOL_USER
SSS_EXASOL_PASSWORD
SSS_GITHUB_TOKEN
SSS_MODEL_PROVIDER_KEYS
SSS_PYPI_BASE_URL=https://pypi.org
SSS_NPM_REGISTRY_URL=https://registry.npmjs.org
SSS_APPROVAL_SIGNING_KEY
SSS_TELEMETRY_ENABLED=false
SSS_STRICT_MODE=true
SSS_RAW_RESPONSE_RETENTION=false
```

`.env.example` contains names and safe defaults only. Real values never enter Git, images, logs, fixtures, or Exasol.

## 18. Technology explicitly excluded from MVP

| Excluded | Reason |
|---|---|
| Electron desktop application | Browser UI is deployable and enough for the demo |
| eBPF/OS-wide process interception | Platform-specific and too risky for seven days |
| Transparent TLS interception | Unnecessary when package managers support registry configuration |
| Kubernetes | One Compose deployment meets the challenge |
| Redis/Celery/Kafka | Exasol job leases and idempotent workers are sufficient |
| Vector database/RAG | Exact identity, provenance, and temporal SQL are the core problem |
| LLM policy judge | Non-deterministic and inappropriate for execution control |
| Dynamic execution of public artifacts | Unsafe and not required to prove the product |
| More ecosystems | Two polished ecosystems make a stronger submission |

## 19. Reference basis

- PyPI project discovery and serials: [PyPI Index API](https://docs.pypi.org/api/index-api/)
- PyPI project metadata: [PyPI JSON API](https://docs.pypi.org/api/json/)
- npm registry configuration: [npm Registry documentation](https://docs.npmjs.com/misc/registry/)
- Public manifest ecosystem coverage: [GitHub dependency graph ecosystems](https://docs.github.com/en/code-security/reference/supply-chain-security/dependency-graph-supported-package-ecosystems)
- Model-controlled tool limitation: [MCP tools and security](https://modelcontextprotocol.io/specification/2024-11-05/server/tools)
- Slopsquatting measurement: [We Have a Package for You!](https://www.usenix.org/conference/usenixsecurity25/presentation/spracklen)
- Source-aware install mediation: [Setup Complete, Now You Are Compromised](https://arxiv.org/abs/2607.15143)
- Confusable package names: [Beyond Typosquatting](https://www.usenix.org/conference/usenixsecurity23/presentation/neupane)
- Static package evidence: [MalGuard](https://www.usenix.org/conference/usenixsecurity25/presentation/gao-xingan)
- Evidence provenance: [in-toto](https://www.usenix.org/conference/usenixsecurity19/presentation/torres-arias)

