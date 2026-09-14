# SSS Agent Guard Demo Design

**Date:** 2026-09-13
**Status:** Approved in chat; awaiting repository-spec review
**Policy:** `sss-hackathon-v3`

## Goal

Deliver a zero-cost, deterministic local demo in which an autonomous coding-agent process attempts
to install a known high-risk synthetic npm package. SSS must intercept the request before `pnpm`
starts, show the agent a concise block explanation, notify a human operator out of band, and accept
an explicit keep-blocked or exact-scope allow-once decision.

The agent workflow, not the Radar dashboard, is the primary demo surface. Radar remains an optional
evidence explorer.

## Demo success criteria

From a clean reset, the demo must prove all of the following:

1. The synthetic package identity is `@sss-demo/reserved-synthetic` in the npm ecosystem at the
   single logical origin `https://npm.demo.sss.test`.
2. Replayed synthetic evidence is persisted in Exasol with the frozen recurrence tuple
   `46/3/8/5/11` and scores `100/95/75`.
3. An unprotected installation of the controlled artifact starts `pnpm` and increments the harmless
   canary exactly once.
4. A noninteractive agent running under `sss protect` attempts the same installation without
   calling SSS directly.
5. The SSS-owned `pnpm` shim parses the original argument vector and asks Guard for a decision.
6. Guard returns `BLOCK` with `REGISTERED_AFTER_HALLUCINATION` and
   `HIGH_GLOBAL_RECURRENCE` under `sss-hackathon-v3`.
7. The shim returns exit code `23`; the immutable real `pnpm` executable has zero starts and the
   canary remains at one.
8. A human operator receives the event and can keep the request blocked, inspect evidence, or issue
   a single-use exact-scope approval.
9. The entire reset-to-block sequence passes twice without changing the expected values.

## Primary demo experience

The recorded demo uses two terminals side by side.

### Agent terminal

The agent is launched with:

```bash
sss protect -- sss-demo-agent
```

The deterministic demo agent narrates a normal dependency decision and invokes:

```bash
pnpm add @sss-demo/reserved-synthetic@1.0.0
```

The protected `PATH` resolves `pnpm` to the SSS shim. On a block, the agent terminal displays:

```text
SSS BLOCKED PACKAGE INSTALLATION
Package: @sss-demo/reserved-synthetic@1.0.0
Registry: https://npm.demo.sss.test
Absence confidence: 100/100
Global target attractiveness: 95/100
Package policy risk: 75/100
Reasons: REGISTERED_AFTER_HALLUCINATION, HIGH_GLOBAL_RECURRENCE
Installation was not started. Human intervention requested: <intervention-id>
```

The text must not claim that the package is malicious. It must say that the temporal pattern is
high risk and that installation was blocked before the package manager started.

### Operator terminal

The operator runs:

```bash
sss intervene --watch
```

When `install.blocked` arrives, the operator sees package identity, requesting agent, exact command,
three scores, reason codes, evidence timestamps, and these actions:

```text
[K] Keep blocked  [I] Inspect evidence  [A] Allow once
```

`Keep blocked` is the safe default. EOF, timeout, invalid input, or no TTY keeps the request blocked.
The operator tool never forwards its prompt to the autonomous agent.

## Architecture

### Integrated branch

Implementation occurs on `codex/agent-guard-demo` in an isolated worktree. The branch combines:

- Teammate 1 intelligence and Exasol work from `codex/teammate-1-intelligence`.
- Teammate 2 enforcement foundations from `origin/Vansh`.
- Recovered frontend commit `8d2c28e` only after the terminal-first vertical slice works.

The seven root configuration conflicts are resolved deliberately, with one shared Python project,
one pnpm workspace, and one lockfile per package manager.

### Guard API

The API exposes strict authenticated endpoints:

- `POST /v1/check` — validate an `InstallRequest`, read evidence, evaluate policy, persist the
  decision, and create an intervention for non-allow outcomes.
- `POST /v1/install-attempts` — record the command fingerprint, decision, child-started state, and
  canary-safe demo metadata.
- `GET /v1/interventions` — list pending interventions for an authenticated operator.
- `GET /v1/interventions/{id}` — inspect the frozen decision and ordered evidence.
- `POST /v1/interventions/{id}/keep-blocked` — resolve the intervention without an approval.
- `POST /v1/approvals` — issue an exact-scope, short-lived approval.
- `POST /v1/approvals/{id}/consume` — consume the approval atomically once.
- `GET /v1/events` — deliver `install.blocked` and `approval.consumed` events with event IDs.
- `GET /health/ready` — verify Exasol connectivity, schema readiness, and policy version.

Unknown JSON fields are rejected. Writes require idempotency keys. Service and operator credentials
remain outside the protected agent environment.

### Command interception

SSS installs shims for `pip`, `pip3`, `python -m pip`, `uv`, `npm`, `pnpm`, `yarn`, and `npx` ahead
of real executables in the protected `PATH`. The demo exercises `pnpm`; the remaining shims use the
same adapter/runner boundary.

Each shim:

1. Receives an argument vector and never evaluates a shell string.
2. Resolves install intent with the frozen core extractor.
3. Calls `/v1/check` with package, exact version, registry, artifact hash, project and agent identity.
4. Starts the immutable configured real executable exactly once only after `ALLOW`.
5. Records whether the child started.
6. Returns `23` on a policy block and a distinct fail-closed code on assessment unavailability.

The runner is dependency-injected so tests can prove zero child starts.

### Intervention and approvals

The noninteractive agent never receives a prompt. A block creates a separate human intervention.
The operator can inspect it and choose:

- `keep_blocked`: close the intervention with no approval.
- `allow_once`: create a signed approval containing exactly package identity, version,
  `registry_origin`, artifact SHA-256, project, expiry, nonce and policy version.

An allow-once approval does not resume a process that was already blocked. The agent or operator
must retry the same command. Guard consumes the matching approval atomically during that retry, and
any changed field, expired grant, reuse, or inactive policy fails closed.

### Demo agent

`sss-demo-agent` is deterministic, visibly labelled as a controlled coding-agent fixture, and needs
no model-provider key. It emits a short agent-style plan and runs the original `pnpm` argument vector
without invoking an SSS API or MCP tool. The same `sss protect -- <command>` launcher remains usable
with a real Codex or Claude executable when an appropriate image and credentials are supplied.

### Local registry and canary

The zero-cost Compose profile includes:

- Exasol Docker Edition for local analytical integration.
- A local npm-compatible registry.
- Local TLS routing for `npm.demo.sss.test`; the same logical origin is used for absence and later
  registration.
- API, registry gateway, canary, protected agent and operator-facing ports bound to localhost.

The synthetic package has one controlled install lifecycle action: send
`DEMO_ONLY_NOT_A_SECRET` to the local canary. It performs no filesystem, credential, process or
external-network access. The protected run is blocked before artifact execution.

Exasol Docker Edition must be named accurately in local-demo claims. Exasol Personal remains the
deployment target when a supported macOS host or user-funded cloud environment is available.

## Data flow

```text
demo agent -> pnpm shim -> Guard API -> Exasol evidence + policy engine
                              |
                              +-> decision + attempt row
                              +-> install.blocked SSE event -> operator CLI
                              +-> exact-scope approval store -> retry/atomic consume

ALLOW -> immutable real pnpm -> local registry gateway -> local registry -> artifact
BLOCK -> exit 23; real pnpm not started; artifact not downloaded
```

## Failure behavior

- Exasol unavailable, schema unready or policy missing: block in strict mode.
- Registry timeout/auth/rate limit/server/TLS/malformed response: `UNKNOWN`, never `ABSENT`.
- Operator disconnected or no response: remain blocked.
- SSE disconnected: operator CLI reconnects using the last event ID and also reconciles pending
  interventions through REST.
- Local registry operation fails: later demo stages remain disabled and return a specific error.
- Reset is fixture-scoped and idempotent; it never deletes unrelated intelligence.
- Any package-manager spawn error is recorded with `child_started=false` unless process creation was
  actually confirmed.

## Security boundaries

- The protected agent is unprivileged, read-only except for the project mount, has no Docker socket,
  no signing key and no Exasol credential.
- Agent egress is limited to API and gateway. Direct registry access fails.
- The gateway permits only approved npm/PyPI origins and bounded metadata/artifact responses.
- The operator credential can resolve interventions but is never placed in agent-visible files or
  environment variables.
- Subprocesses always use argument vectors with `shell=False`.
- Real package-manager paths must be absolute, preconfigured and outside the shim directory.

## Testing and delivery gates

Implementation follows test-driven slices. Each slice is committed only after its focused tests and
the combined regression suite pass.

1. **Integration gate:** both branches merge; all previous Python and Node tests pass together.
2. **API gate:** contract examples validate; readiness checks real Exasol; unknown fields,
   unauthenticated requests and missing idempotency keys fail.
3. **Guard gate:** unsafe `pnpm add` returns `23`, records a block, and starts zero children; approved
   established packages start exactly once.
4. **Intervention gate:** operator receives a live event; keep-blocked is fail-safe; allow-once
   cannot be widened or replayed.
5. **Boundary gate:** protected agent has no direct registry egress; permitted artifacts use the
   gateway; blocked artifacts are never downloaded.
6. **Demo gate:** reset/replay/register/unprotected/protected produces `46/3/8/5/11`, `100/95/75`,
   total canary `1`, protected child starts `0`.
7. **Rehearsal gate:** the complete terminal-first story passes twice from clean reset with model
   keys absent.
8. **Release gate:** Ruff, strict mypy, pytest, Node tests/typecheck/build, dependency audit, secret
   scan, Compose validation and `git diff --check` all pass.

## Non-goals for this vertical slice

- A cloud deployment that could incur user charges.
- Host-root or macOS/Windows tamper resistance.
- Automatic permanent trust.
- Dynamic execution of unknown public packages.
- Rebuilding the Radar dashboard before the agent interception path is complete.
- Requiring MCP cooperation from the agent.
