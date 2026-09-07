# SSS — Stop Slop Squatting: Architecture

**Version:** Hackathon MVP v3  
**Primary track:** AI Trust, Safety & Governance  
**Secondary track:** AI Agents That Get Things Done  
**Build window:** Seven days  
**Deployment:** Docker Compose locally; the same containers can run on AWS or Azure

## 1. Product definition

SSS is an agent-independent software-supply-chain security gateway for AI-assisted development. It continuously discovers package names that models recommend while those names do not exist, keeps the unregistered names private, watches for later registration, and blocks dangerous installation attempts before package code runs.

The defining signal is temporal:

```text
model recommends a name
        ↓
registry proves it absent
        ↓
the pattern repeats across models, prompts, users, or public artifacts
        ↓
the name is registered later
        ↓
an agent attempts to install it
```

SSS calls this a **registration-after-hallucination transition**. It is a strong supply-chain risk signal, but not by itself proof of malicious intent.

### 1.1 Product surfaces

- **SSS Network:** continuously updated global intelligence from controlled model probes, public software artifacts, opt-in protected-agent observations, and registry state.
- **SSS Radar:** private Exasol-powered analytics for recurrence, evidence provenance, registry transitions, and enforcement outcomes.
- **SSS Guard:** local deterministic policy service.
- **SSS Protect:** launches Codex, Claude Code, or another agent in a protected workspace and mediates package installation.
- **SSS MCP:** optional tools for proactive checks and explanations. MCP is never the security boundary.

### 1.2 Correct product claims

SSS may say:

- “This package does not currently exist in the selected registry.”
- “SSS directly observed this name being recommended while absent.”
- “This name was repeatedly observed across independent sources.”
- “This package was registered after verified absence observations.”
- “Installation was blocked before the package manager started.”
- “Static inspection found these suspicious package characteristics.”

SSS must not call a package malicious solely because it was absent or registered later. The UI uses **nonexistent**, **verified hallucination**, **suspected slopsquat**, or **confirmed malicious** only when corresponding evidence exists.

## 2. MVP scope

### 2.1 Supported ecosystems

| Ecosystem | Registry | Package-manager adapters |
|---|---|---|
| Python | PyPI and approved private PEP 503 indexes | `pip`, `pip3`, `python -m pip`, `uv`, Poetry manifests |
| JavaScript | npm-compatible registries | `npm`, `pnpm`, `yarn`, `npx` |

`pnpm`, `yarn`, and `npx` are npm-ecosystem clients, not separate registries. Likewise, `uv` and Poetry normally resolve Python distributions.

### 2.2 In scope

- Controlled probe corpus covering at least three model configurations and 48 coding tasks.
- Exact model, version, parameters, prompt version, response hash, and run time.
- Public GitHub ingestion limited to public manifests, lockfiles, issues, and public CI excerpts permitted by the API.
- Opt-in telemetry from protected SSS installations.
- Reproducible PyPI snapshots and timestamped PyPI/npm checks.
- Recurrence and transition analytics in Exasol.
- Private watchlist; raw unregistered names never appear in a public feed.
- Autonomous pre-install blocking in a Linux/Docker protected workspace.
- Out-of-band web notification and exact-scope “allow once” approval.
- Safe local-registry attack simulation.

### 2.3 Explicitly out of scope

- Crawling private prompts, private repositories, or claiming to crawl the entire internet.
- Publishing a searchable list of attractive unregistered names.
- Windows/macOS tamper-resistant enforcement during the hackathon.
- Protection against host root access that can disable SSS itself.
- Full malware classification, arbitrary dynamic execution, or automatic attribution.
- Cargo, Maven, NuGet, Go, RubyGems, Composer, and system package managers.
- Interception of every download mechanism such as `curl | sh`.

## 3. Success criteria

1. Extract and normalize install requests for both ecosystems.
2. Label a verified hallucination only with an attributable model recommendation and conclusive absence at observation time.
3. Treat rate limits, network faults, authentication failures, and server errors as `UNKNOWN`, never absence.
4. Aggregate global recurrence without merging ecosystems or npm scopes.
5. Detect absent-to-registered transitions on a schedule.
6. Block a risky install under `sss protect -- <agent>` without agent cooperation.
7. Default non-interactive `REVIEW` decisions to block.
8. Bind “allow once” to package, version, registry, artifact hash, project, and expiry.
9. Persist and query intelligence and enforcement evidence in Exasol.
10. Run the deterministic demo without live model providers.

## 4. Threat model

### 4.1 Primary attacker

An attacker discovers names that coding models repeatedly invent, registers one on a public registry, publishes a harmful artifact, and waits for an autonomous coding agent to install it.

### 4.2 Protected assets

- Developer credentials, source code, and private repositories.
- SSH keys, cloud credentials, browser sessions, and local files.
- CI secrets and deployment tokens.
- Integrity of manifests and lockfiles.

### 4.3 Techniques considered

- Registering a previously absent hallucinated name.
- Typosquatting, combosquatting, namespace confusion, and import/distribution confusion.
- New releases with install/build scripts.
- Alternate indexes, extra indexes, direct tarballs, Git URLs, and local paths.
- Lockfile or registry-source manipulation.
- Bypassing an advisory MCP check.
- Shell injection inside package-manager arguments.

### 4.4 Trust boundary

The strongest guarantee exists inside an SSS-protected unprivileged container or workspace. `sss protect` controls package-manager discovery, registry configuration, and allowed network destinations. A host process with root privileges can defeat a user-space control; SSS must state this limitation.

## 5. System context

```text
                          SSS NETWORK

 Controlled model probes ──────────────┐
 Public GitHub intelligence ───────────┤
 Opt-in SSS Guard events ──────────────┼──> Ingestion + validation
 PyPI/npm observations ────────────────┘              │
                                                       ▼
                                                Exasol evidence graph
                                                       │
                                      ┌────────────────┴───────────────┐
                                      ▼                                ▼
                                  SSS Radar                    Transition monitor
                                                                       │
                                                                       ▼
                                                            signed policy feed/API

                         PROTECTED WORKSPACE

 Human ──> sss protect -- codex/claude
                         │
                         ▼
                  unprivileged agent
                         │
             tries pip/npm/pnpm/uv/...
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
     command shims              registry gateway
            └────────────┬────────────┘
                         ▼
                    SSS Guard API
                         │
               ALLOW / BLOCK / REVIEW
                         │
              ┌──────────┴───────────┐
              ▼                      ▼
       package manager       Radar notification
       starts only if safe   and human approval UI
```

## 6. Intelligence acquisition

### 6.1 Controlled model probes

The probe worker runs versioned coding tasks against configured model providers. Each run stores provider, exact model identifier, relevant parameters, prompt-suite version, prompt/response hashes, retention class, extracted mentions, locations, confidence, and registry evidence captured immediately after extraction.

Repeated trials are necessary. A single response is anecdotal; cross-run and cross-model recurrence is the useful signal.

### 6.2 Opt-in protected-agent telemetry

SSS Guard contributes package-attempt observations only after explicit opt-in. The event contains canonical package identity, requested version/source, agent family, policy version, timestamp, and installation-attempt identifier. It excludes prompts, source code, environment variables, repository contents, usernames, and filesystem paths.

Telemetry proves an agent attempted an installation; it does not prove the agent invented the name. It therefore has separate provenance from controlled probes.

### 6.3 Public internet intelligence

The MVP scans public software-development artifacts rather than arbitrary pages:

- Dependency manifests and lockfiles in public repositories.
- Public issues containing explicit install commands or resolution errors.
- Public CI excerpts containing conclusive package-not-found failures.
- Licensed research corpora with documented provenance.

Public mentions are discovery signals. SSS independently validates registry state and never labels them model hallucinations without direct model evidence.

### 6.4 Registry acquisition

#### PyPI

- Capture a sorted, canonicalized snapshot from the PyPI Simple JSON Index.
- Store `_last-serial`, capture time, project count, source URL, content SHA-256, and normalization version.
- Use the project JSON or Simple project endpoint for live checks.

#### npm

- Query the configured npm registry metadata endpoint for the exact canonical name, including encoded scopes.
- Store response status, registry URL, selected headers, observation time, and evidence hash.
- A timestamped conclusive `404` is the historical absence proof. The MVP does not claim an authoritative historical npm snapshot it does not possess.

### 6.5 Continuous scheduling

| Job | Cadence |
|---|---|
| High-attractiveness absent-name recheck | Every 15 minutes |
| Other private watchlist recheck | Every 6 hours |
| Controlled probe suite | Daily and on model-version change |
| Public-source discovery | Hourly within API quotas |
| PyPI baseline refresh | Daily; retain every version |
| Newly registered artifact inspection | Immediately after transition |

Jobs are idempotent, cursor-based, rate-limited, and safe to retry. The deterministic demo replays observations into a local registry through the same interfaces.

## 7. Extraction and normalization

### 7.1 Python

- Explicit `pip`, `python -m pip`, and `uv` arguments.
- PEP 508 requirements through `packaging.requirements.Requirement`.
- `requirements*.txt`, `pyproject.toml`, Poetry sections, and supported locks.
- Python AST imports after standard-library exclusion.
- Versioned aliases such as `cv2 → opencv-python` and `sklearn → scikit-learn`.

### 7.2 npm

- `npm install`, `npm i`, `pnpm add`, `yarn add`, and `npx` arguments.
- `package.json`, `package-lock.json`, `pnpm-lock.yaml`, and `yarn.lock` direct requirements.
- Preserve scopes in names such as `@scope/name`.
- Store versions, tags, aliases, workspaces, Git sources, URLs, and paths separately.

### 7.3 Canonical identity

```text
(ecosystem, canonical_registry_origin, canonical_package_name)
```

PyPI normalization follows PEP 503. npm names are lowercase and scopes remain intact. Identical strings in different ecosystems never merge.

### 7.4 Safe parsing

SSS accepts argument vectors, never evaluates shell strings, and executes allowed children with `shell=False`. Pipes, redirects, substitutions, chained commands, and unsupported installers are rejected.

## 8. Evidence state machine

```text
EXTRACTED
  ├─ invalid/local/stdlib/unresolved alias ──> EXCLUDED or AMBIGUOUS
  └─ valid distribution name
          ├─ registry 200 ──> REGISTERED
          ├─ conclusive 404 + direct model evidence ──> VERIFIED_HALLUCINATION
          ├─ conclusive 404 + other provenance ──> VERIFIED_ABSENT
          └─ timeout/429/5xx/auth/DNS/TLS ──> UNKNOWN

VERIFIED_HALLUCINATION or VERIFIED_ABSENT
          ├─ later 404 ──> remain absent
          ├─ later 200 with later first release ──> REGISTERED_AFTER_ABSENCE
          └─ inconclusive ──> retain state + append UNKNOWN evidence
```

Historical evidence is immutable. A later `200` creates a transition; it never rewrites the earlier `404`.

## 9. Evidence indices and policy

Policy version: `sss-hackathon-v3`. These are deterministic engineering indices, not probabilities.

### 9.1 Absence confidence

A conclusive registry `404`, valid canonical name/origin, and completed exclusions produce `100`. An inconclusive result has no score and state `UNKNOWN`.

### 9.2 Global target attractiveness

| Factor | Maximum points |
|---|---:|
| Distinct verified model recommendations | 35 |
| Distinct model configurations | 20 |
| Opt-in protected-agent attempts | 20 |
| Public failed dependency references | 10 |
| Persistence across observation days | 10 |
| Explicit install/manifest context | 5 |

The v3 calculation is exact and capped per factor:

```text
verified model recommendations = min(35, distinct_verified_runs)
model configurations           = 0 / 10 / 15 / 20 for 0 / 1 / 2 / 3+
protected-agent attempts       = min(20, floor(distinct_clients × 2.5))
public failed references       = min(10, distinct_public_sources)
observation-day persistence    = min(10, distinct_observation_days)
explicit install context       = 5 when present, otherwise 0
```

Counts are deduplicated by source/run. A rotating client pseudonym contributes at most `2.5` points, and public references are deduplicated by repository plus file/job, preventing one source from flooding the score.

### 9.3 Package policy risk after registration

| Factor | Points |
|---|---:|
| Registered after verified hallucination/absence | 45 |
| First release at most 72 hours old | 15 |
| Target attractiveness at least 60 | 15 |
| Unapproved registry, direct source, or source mismatch | 15 |
| Install/build hooks or bounded suspicious static sequence | 10 |

### 9.4 Hard rules

1. Conclusively absent request: `BLOCK / PACKAGE_NOT_FOUND`.
2. Registry or policy unavailable in strict mode: `BLOCK / ASSESSMENT_UNAVAILABLE`.
3. Unapproved/ambiguous/VCS/direct/local source without an explicit rule: `BLOCK`.
4. Registered after verified hallucination with attractiveness at least `60`: `BLOCK`.
5. Registered after verified absence below the hard threshold: `REVIEW`.
6. Established package from an approved source with no hard rule: `ALLOW`.

For non-interactive agents, `REVIEW` resolves to `BLOCK` until a human grants approval.

## 10. Enforcement architecture

### 10.1 `sss protect`

```bash
sss protect -- codex
sss protect -- claude
```

The launcher creates or enters a protected workspace containing an unprivileged agent, SSS-owned shims first in `PATH`, npm/PyPI configuration pointed at the local gateway, registry egress allowlists, project identity, short-lived session credentials, and audit events.

### 10.2 Command shims

Shims intercept direct installation intent and preserve direct-versus-transitive context. They parse the request, call Guard, and start the real manager only after `ALLOW`.

### 10.3 Registry gateway

The gateway is a configured npm/PEP 503-compatible proxy, not a TLS man-in-the-middle. It evaluates metadata and artifacts, catches transitive dependencies, enforces source policy, and forwards only allowed requests to approved upstreams.

Shims provide command intent; the gateway catches dependency resolution and makes bypass harder inside the protected network boundary.

### 10.4 Human decision channel

Guard posts events to Radar over Server-Sent Events. The user sees the agent, command, identity, source, evidence timeline, and reason.

- **Keep blocked** — default.
- **Inspect evidence** — read-only.
- **Allow once** — signed, short-lived, and bound to package, exact version, registry, artifact SHA-256, project, and expiry.

There is no permanent global-trust button in the MVP.

### 10.5 Optional MCP

- `sss.check_package`
- `sss.explain_decision`
- `sss.find_safe_alternatives`
- `sss.report_suspected_hallucination`

An agent may call them before proposing a dependency. Guard still evaluates the actual installation independently.

## 11. Core domain model

```python
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

class Ecosystem(StrEnum):
    PYPI = "pypi"
    NPM = "npm"

class EvidenceProvenance(StrEnum):
    MODEL_PROBE = "model_probe"
    AGENT_INSTALL_ATTEMPT = "agent_install_attempt"
    PUBLIC_MANIFEST = "public_manifest"
    PUBLIC_CI_FAILURE = "public_ci_failure"
    USER_REPORT = "user_report"

class RegistryStatus(StrEnum):
    REGISTERED = "registered"
    ABSENT = "absent"
    UNKNOWN = "unknown"

class CandidateStatus(StrEnum):
    AMBIGUOUS = "ambiguous"
    VERIFIED_ABSENT = "verified_absent"
    VERIFIED_HALLUCINATION = "verified_hallucination"
    REGISTERED = "registered"
    REGISTERED_AFTER_ABSENCE = "registered_after_absence"

class Decision(StrEnum):
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"

@dataclass(frozen=True)
class PackageIdentity:
    ecosystem: Ecosystem
    registry_origin: str
    canonical_name: str

@dataclass(frozen=True)
class InstallRequest:
    request_id: str
    project_id: str
    agent_family: str
    package: PackageIdentity
    version_spec: str | None
    direct_url: str | None
    artifact_sha256: str | None
    is_direct: bool

@dataclass(frozen=True)
class EvidenceScores:
    absence_confidence: int | None
    target_attractiveness: int
    package_policy_risk: int

@dataclass(frozen=True)
class PolicyDecision:
    decision_id: str
    request_id: str
    decision: Decision
    reason_codes: tuple[str, ...]
    scores: EvidenceScores
    policy_version: str
    expires_at: datetime | None
```

Only `PolicyDecision.decision` controls execution.

## 12. Exasol analytical model

### 12.1 Evidence tables

- `REGISTRY_BASELINES`: ecosystem, baseline ID, source, cursor/serial, captured time, count, hash.
- `MODEL_CONFIGURATIONS`: provider, model ID, parameters, first/last seen.
- `PROMPT_TASKS`: suite version, category, prompt hash, expected ecosystem.
- `MODEL_RUNS`: configuration, prompt, time, response hash, status.
- `PACKAGE_MENTIONS`: canonical identity, provenance, context, confidence, source/run, time.
- `REGISTRY_CHECKS`: identity, endpoint, state, HTTP status, time, response hash, error class.
- `CANDIDATES`: status, first/last absence, first registration, disclosure class.
- `PUBLIC_SOURCE_OBSERVATIONS`: public URL hash, source kind, policy metadata, time.
- `CLIENT_INSTALL_OBSERVATIONS`: privacy-safe opt-in event, pseudonym, agent, requested source.
- `PACKAGE_RELEASES`: version, upload time, source, artifact hashes, first seen.
- `STATIC_FINDINGS`: artifact hash, rule ID, severity, file, bounded evidence.

### 12.2 Enforcement tables

- `POLICY_RULES`: versioned deterministic rules and effective time.
- `POLICY_DECISIONS`: request, indices, decision, reasons, policy version.
- `INSTALL_ATTEMPTS`: command fingerprint, agent, project pseudonym, decision, child-started flag.
- `APPROVAL_GRANTS`: exact scope, signer, creation/expiry, one-time consumption.
- `EVIDENCE_ATTESTATIONS`: canonical JSON hash chaining decision evidence.

### 12.3 Required views

- `V_VERIFIED_HALLUCINATIONS`
- `V_GLOBAL_RECURRENCE`
- `V_MODEL_PACKAGE_HALLUCINATION_RATE`
- `V_REGISTRATION_TRANSITIONS`
- `V_HIGH_ATTRACTIVENESS_WATCHLIST`
- `V_SOURCE_POLICY_VIOLATIONS`
- `V_PACKAGE_EVIDENCE_TIMELINE`
- `V_GUARD_OUTCOMES`
- `V_RADAR_PRIVATE`
- `V_RADAR_PUBLIC_AGGREGATES`

The public view contains counts and synthetic examples only; it excludes raw unregistered names.

## 13. Service interfaces

### 13.1 Intelligence API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/observations/model` | Store authenticated controlled-probe evidence |
| `POST` | `/v1/observations/client` | Store an opted-in agent attempt |
| `POST` | `/v1/observations/public` | Store public-source discovery evidence |
| `POST` | `/v1/registry/checks` | Persist registry evidence |
| `GET` | `/v1/radar` | Private ranked intelligence |
| `GET` | `/v1/packages/{ecosystem}/{name}` | Evidence timeline |
| `GET` | `/v1/events` | SSE transition and enforcement events |

### 13.2 Guard API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/check` | Evaluate a complete install request |
| `POST` | `/v1/install-attempts` | Record execution/non-execution |
| `POST` | `/v1/approvals` | Create exact-scope approval |
| `POST` | `/v1/approvals/{id}/consume` | Atomically consume it once |

```json
{
  "decision": "block",
  "reason_codes": ["REGISTERED_AFTER_HALLUCINATION", "HIGH_GLOBAL_RECURRENCE"],
  "scores": {
    "absence_confidence": 100,
    "target_attractiveness": 95,
    "package_policy_risk": 75
  },
  "summary": "Registered 43 minutes ago after 46 verified absent recommendations.",
  "child_process_allowed": false,
  "policy_version": "sss-hackathon-v3"
}
```

## 14. Privacy and abuse prevention

- Raw unregistered names are `RESTRICTED_TARGET_INTELLIGENCE`.
- Public APIs never enumerate the watchlist.
- Client telemetry is disabled until opt-in and contains no prompt/source content.
- Client pseudonyms rotate; usernames, paths, location, and machine IDs are not stored.
- Public-source evidence retains provenance and removal metadata.
- Provider prompts/responses use configurable retention and encryption.
- Private Radar access is authenticated and audited.
- Rate limits and per-source deduplication prevent score manipulation.
- Demo names are synthetic and clearly labelled.

## 15. Artifact inspection

Inspection occurs only after a watched name is registered and before allowing installation:

- Maximum compressed size: 20 MiB.
- Maximum expanded size: 100 MiB.
- Maximum entries: 10,000.
- Maximum individual file: 5 MiB.
- Reject traversal, symlinks, device files, and decompression bombs.
- Detect Python build/setup hooks and npm lifecycle scripts.
- Apply bounded static rules for credential access, spawning, obfuscation, and network behavior.

Static findings are evidence, not a malware verdict. Production never dynamically runs an unknown public artifact. Only the synthetic fixture executes inside the isolated demo lab.

## 16. Reliability

| Failure | Required behaviour |
|---|---|
| Registry `429`, timeout, `5xx`, DNS, TLS, malformed response | Store `UNKNOWN`; bounded retry; never infer absence |
| Exasol unavailable | Readiness fails; strict mode blocks |
| Intelligence API unavailable | Use fresh signed cache or strict-mode block |
| GitHub quota exhausted | Save cursor and resume; Guard remains available |
| Model provider unavailable | Monitor registries and replay corpus; mark probe delayed |
| Approval UI unavailable | Keep `REVIEW` blocked |
| Duplicate job/event | Idempotency key returns prior result |
| Stale evidence | Show age and refresh before allowing a new package |

## 17. Deployment

Docker Compose services:

- `exasol`, `api`, `worker`, `web`, and `gateway`.
- `demo-npm-registry`, `demo-pypi-registry`, `canary`, and `protected-agent-demo`.

The same images can run on an AWS or Azure VM. Exasol Personal remains the analytical system of record. The local machine installs only the thin `sss` CLI, which creates a protected Docker workspace and connects to the chosen SSS deployment.

## 18. Testing and measurement

### 18.1 Tests

- Cross-ecosystem normalization, scoped packages, commands, and manifests.
- Standard-library/alias exclusions and shell-injection rejection.
- Registry truth tables and immutable temporal transitions.
- Score boundaries, hard rules, and strict-mode failure.
- Approval signature, scope, expiry, and one-time consumption.
- Archive limits and traversal rejection.
- Exasol migrations, views, recurrence, and transition queries.
- Public-source cursors/deduplication and telemetry redaction.
- Proof that blocked commands never spawn a child process.
- Gateway denial of unapproved registries and direct URLs.

### 18.2 End-to-end invariant

```text
reset synthetic evidence
→ replay global observations
→ prove synthetic name absent
→ show private Radar recurrence
→ register it on local npm registry
→ detect transition
→ protected autonomous agent attempts pnpm add
→ SSS blocks without MCP or agent cooperation
→ UI receives event
→ protected canary count remains zero
```

An unprotected disposable container may install the synthetic artifact once to produce one harmless canary event.

### 18.3 Reported metrics

- Extraction precision/recall on a labelled cross-ecosystem holdout.
- Micro/macro package-hallucination rate for controlled probes.
- Unknown-oracle rate and global recurrence.
- Public-signal precision after validation.
- Transition-detection latency and Guard p50/p95 latency.
- Blocked-child-process invariant and false-positive review count.

Every metric names corpus version, registry, baseline/check time, and model configuration.

## 19. Demo contract

One reserved synthetic npm package uses fixed evidence:

- 46 verified model recommendations.
- 3 model configurations.
- 8 opted-in protected-agent attempts.
- 5 public failed dependency references.
- 11 observation days.
- Absence confidence `100`.
- Target attractiveness `95`.
- Later local-registry registration.
- Package policy risk `75`.
- Decision `BLOCK` under `sss-hackathon-v3`.

The protected agent runs non-interactively and does not call SSS MCP. It attempts `pnpm add <synthetic-name>`; SSS independently blocks it.

## 20. Architecture decisions

- **Enforcement is independent of MCP:** an advisory tool can be bypassed.
- **Two ecosystems, multiple adapters:** implement PyPI/npm once, then adapt their clients.
- **Historical evidence is immutable:** later registration creates a transition.
- **Every observation has provenance:** only direct model evidence earns the hallucination label.
- **The watchlist is private:** disclosure would help attackers.
- **Policy is deterministic and pre-execution:** an LLM never decides allow/block.
- **Docker is the MVP security boundary:** honest, reproducible, and buildable in seven days.
- **Exasol is the analytical system of record:** the core workload is temporal correlation across many evidence streams.

## 21. Post-hackathon roadmap

- Signed offline policy feeds and native macOS/Windows controls.
- Organization registry proxies, CI admission, and GitHub App.
- Cargo, Maven, NuGet, Go, RubyGems, and Composer.
- Privacy-preserving cross-organization recurrence aggregation.
- Responsible registry/maintainer notification workflow.
- Curated analyst verdicts and confirmed-malware integrations.
- IDE extensions and native Codex/Claude integrations.
