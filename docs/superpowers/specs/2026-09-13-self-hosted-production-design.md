# Single-Organization Self-Hosted Production Design

## Purpose

Turn Stop Slop Squatting (SSS) from a deterministic demonstration into a production-capable,
single-organization service. Any supported coding agent can be launched through the local SSS
boundary and have package installation intent evaluated independently of agent cooperation.

This design preserves the controlled fixture as an explicit demo profile. Production decisions
must never depend on the fixture or silently fall back to it.

## Deployment boundary

The supported production target is one organization operating one Linux deployment. The core
services are FastAPI, the worker, the registry gateway, the web application, a TLS reverse proxy,
and Exasol. They may run on one host or on organization-managed hosts connected by a private
network. The design does not implement multi-tenant data isolation, billing, or public SaaS
account management.

The production profile connects to an organization-operated, production-supported Exasol
installation and does not provision the database itself. Exasol Personal is a free single-user
evaluation/development option, while Exasol Docker Edition is limited to local development and
testing; neither is represented as a supported production database. The zero-cost qualification
profile uses local Exasol Docker Edition, and the application can also be evaluated against Exasol
Personal when an operator supplies its connection details. Cloud provisioning is never performed
automatically. See the official [editions overview](https://docs.exasol.com/db/7.1/get_started/exasol_editions.htm)
and [Exasol Personal quick start](https://docs.exasol.com/db/latest/get_started/quick_start_guide.htm).

## Supported user experience

An operator provisions a scoped agent token and configures the CLI once:

```bash
sss configure --server https://sss.company.internal --token <agent-token>
sss protect -- codex
sss protect -- claude
sss protect -- <other-agent-command>
```

The protected environment intercepts supported Python and npm ecosystem installation intent:

- `pip`, `pip3`, and `python -m pip`
- `uv`
- Poetry commands and manifests
- `npm`
- `pnpm`
- Yarn
- `npx`

Direct install intent is evaluated by command shims. Package resolution and transitive artifacts
are constrained through the configured SSS registry gateway. An agent running outside the wrapper,
a host administrator, or an unsupported ecosystem is outside the security boundary.

## Production and demo modes

Production and demo composition are explicit and disjoint.

### Production

- Requires a reachable Exasol schema at the current migration version.
- Requires the configured policy version to be available.
- Loads arbitrary package evidence through general repository interfaces.
- Persists decisions, attempts, interventions, idempotency claims, approval state, and worker cursors.
- Refuses to start when required configuration is absent or contains demo defaults.
- Never imports or loads `demo/fixtures/fixed-intelligence.json`.

### Demo and test

- May replay the synthetic fixture and controlled registry package.
- May use in-memory stores in isolated unit tests.
- Is visibly labelled synthetic.
- Cannot be selected implicitly by missing production configuration.

## Runtime architecture

```text
model/public/client observations
        |
        v
authenticated ingestion API
        |
        v
immutable Exasol evidence and registry observations
        |
        v
worker validation, registry rechecks, transitions and durable cursors
        |
        v
general Exasol evidence facts -> deterministic scoring -> PolicyEngine
        |
        +---- ALLOW ----> immutable real package manager / gateway
        |
        +---- BLOCK ----> persisted attempt + intervention + redacted SSE
```

The policy engine remains a pure deterministic component. The production evidence provider loads
facts for the requested canonical package identity, converts them to a typed `PolicyContext`, and
does not contain package-name or score constants. Scoring uses the canonical functions in
`sss_core.evidence.scoring` rather than values stored in a demo fixture.

Every decision persists the evidence data-as-of time, policy version, reason codes, scores,
canonical request, and evidence attestation. A process restart must not change or erase the
decision record.

## Evidence ingestion and collection

Authenticated, strictly validated endpoints accept model-probe, opted-in client, public-source,
and registry observations. Each route requires an idempotency key and a credential with the
corresponding scope. Provenance is assigned by the route and cannot be supplied or upgraded by the
caller.

The worker provides runnable entrypoints for:

- registry baselines and watchlist rechecks;
- public-source collection with durable cursors and quota state;
- controlled model probes through a configured OpenAI-compatible HTTP endpoint;
- transition detection and materialized analytical refresh;
- retention cleanup for data classes whose configured lifetime has expired.

Replay providers remain available only for demo and test execution. Provider errors preserve the
cursor and produce typed job outcomes; they cannot turn an unknown registry result into absence.

## Authentication and authorization

Service credentials use separate scopes for `agent:check`, `collector:write`, `radar:read`,
`approval:write`, and `operator:intervene`. `SSS_CREDENTIALS_FILE` is a root-readable JSON file
containing credential IDs, SHA-256 token digests, enabled state, and exact scopes. Comparisons are
constant-time. `sss admin token generate` creates a cryptographically random raw token and prints
the corresponding JSON entry; the raw token is shown once and is never logged or stored by the
server.

The browser and private Radar sit behind Caddy HTTP Basic authentication using a bcrypt password
hash supplied through a secret file. Caddy removes client-supplied `X-SSS-Operator` and
`X-SSS-Proxy-Token` headers, then injects the authenticated username and a shared proxy token. The
API validates that token in constant time. The API container is reachable only on internal
networks, so clients cannot bypass Caddy to forge trusted headers. The production browser surface
is read-only; approvals and intervention mutations remain authenticated CLI/API operations. Health
liveness may be unauthenticated; readiness returns no private data.

Public aggregate routes never enumerate absent names. Production does not expose synthetic demo
routes unless the demo profile is explicitly enabled.

## Enforcement boundary

The protected agent runs as a non-root user with a read-only root filesystem, no Docker socket,
no administrative or approval-signing credentials, dropped capabilities, bounded resources, and
no direct public network egress. It can reach the Guard API and registry gateway only.

Shims resolve immutable real executable paths during image construction. They parse argument
vectors without a shell, preserve direct/transitive and source information, and start the real
manager exactly once only after `ALLOW`. `BLOCK` exits with code `23`. Noninteractive `REVIEW`
becomes `BLOCK`.

The gateway accepts only configured upstream origins, applies metadata and archive limits, and
does not permit fallback to a public registry. Direct URLs, VCS sources, local paths, alternate
registries, missing artifact hashes, and unknown sources are denied unless policy explicitly
allows their exact scope.

## Durable operational state

Exasol is the system of record for evidence and analytical views. Production migrations add
durable tables and repositories for:

- install attempts and policy decisions;
- interventions and their terminal state;
- idempotency request hashes and response references;
- issued and consumed approval nonces;
- worker cursors, leases, outcomes, and data freshness;
- scoped credential identities and audit events where appropriate.

Writes use parameterized queries and transactions. Conflicting reuse of an idempotency key fails
without altering the original record. Approval consumption is an atomic compare-and-set operation.
Worker leases prevent overlapping execution of the same scheduled job.

## API and UI

Private APIs provide paginated packages, evidence timelines, Radar rows, decisions, attempts,
interventions, approvals, collector health, and data freshness. They read general Exasol
repositories rather than constructing fixture responses. List endpoints have stable ordering and
bounded limits.

SSE events include monotonic persisted IDs. Browser-safe events contain only redacted identifiers
and state changes. Reconnection with `Last-Event-ID` resumes from durable state. The UI remains an
operator surface; enforcement does not depend on it.

The `origin/frontend` animated dock and Radar interaction commits will be merged into the current
UI. Conflicts are resolved in favor of production API contracts, accessibility, reduced motion,
and the terminal-first enforcement story.

## Failure behavior

- Missing, stale, or incorrectly migrated Exasol: readiness fails and Guard blocks.
- Registry timeout, authentication failure, `429`, `5xx`, DNS, TLS, or malformed response:
  `UNKNOWN`; strict noninteractive policy blocks.
- Provider outage: prior evidence remains attributed and marked stale; affected new checks block.
- API restart: durable attempts, interventions, idempotency and approvals remain available.
- Gateway outage: resolution fails without direct-registry fallback.
- Invalid scope: `401` or `403` without private package disclosure.
- UI outage: CLI enforcement continues.
- Demo fixture present on disk in production: ignored; importing it from a production composition
  path is a test failure.

## Operations

The production Compose profile pins every public application image by digest, expects an external
production-supported Exasol endpoint, and exposes only the TLS reverse proxy. The separate
qualification profile starts local Exasol Docker Edition for no-cost development and test. Both
profiles include health checks, restart policies, resource limits, read-only filesystems where
possible, internal networks, log rotation, and named persistent volumes. Secrets are supplied from
files or the environment and never committed.

Operator documentation covers initial provisioning, migration, credential generation and
rotation, worker startup, readiness, backup, restore, upgrade, rollback, and non-destructive
shutdown. Backup/restore validation must use a disposable schema or volume and compare row counts,
migration version, and a known decision attestation.

## Active-branch integration policy

`codex/agent-guard-demo` is the integration base. Current branch inventory shows:

- `codex/teammate-1-intelligence`: already contained;
- `origin/Vansh`: already contained;
- `origin/frontend`: two unique commits requiring integration;
- `main`: the final target.

Before the final merge, remote references are fetched again. Any newly divergent branch is
reviewed and merged into the integration branch if it contains project work not already represented.
Branches that are ancestors are recorded as contained and are not merged redundantly. The final
validated integration branch is merged into `main` without rewriting shared history, then `main`
is pushed to `origin`.

## Verification and release gates

Release requires all of the following:

- unit, integration, security, E2E, browser, lint, and strict type checks pass;
- migrations are idempotent on live Exasol;
- arbitrary-package evidence and decisions survive API restart;
- every supported client has allow, block, hostile-input, and no-child-process coverage;
- scoped authentication, authorization, idempotency, approval expiry and replay tests pass;
- protected agents have no public egress, root privileges, Docker socket, or signing credentials;
- production Compose starts cleanly without demo configuration and passes TLS/readiness checks;
- dependency, secret, and available container-image scans report no unresolved high findings;
- backup and restore complete with verified data equivalence;
- two complete protected-agent rehearsals leave the canary unchanged;
- frontend tests, production build, accessibility checks, and reduced-motion behavior pass;
- every active branch is reconciled and `git diff --check` is clean.

The release documentation must state the supported ecosystems and the enforcement boundary. It
must not claim protection for unwrapped agents, hostile host administrators, or unsupported package
managers.
