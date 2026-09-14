# SSS demo video script

Target duration: 2 minutes 40 seconds. Record at 1080p or higher with terminal text at least 24 px.
Use only the synthetic package and local registry. Hide all real tokens, usernames and filesystem
paths. The main frame is the protected coding agent; show Radar only after the block.

## Before recording

Complete `docs/operations/agent-demo.md` through registry seeding. Reset Exasol/demo state and the
canary. Open three terminals named **AGENT**, **OPERATOR** and **PROOF**. Put the browser on the
authenticated private Radar package detail page, but leave it behind the terminals.

Validation rule: the fixed identity is `@sss-demo/reserved-synthetic@1.0.0`, the origin is
`https://npm.demo.sss.test`, evidence is `46/3/8/5/11`, scores are `100/95/75`, and the canary count
is zero.

## 0:00–0:20 — Problem

Say: “Coding agents install dependencies at machine speed. If a model repeatedly invents a plausible
package name, an attacker can register it later. A normal registry lookup sees a real package and
misses the history.”

Show the **AGENT** terminal and identify it as a controlled coding agent running inside the same
protected boundary available to local Codex or other command line agents.

## 0:20–0:52 — Unsafe install is stopped

In **OPERATOR**, start:

```bash
SSS_API_URL=http://127.0.0.1:8000 SSS_API_TOKEN=demo-agent-token \
  .venv/bin/sss intervene --watch
```

In **AGENT**, run the protected fixture:

```bash
docker compose -f infra/docker/demo.compose.yaml run --rm protected-agent
```

Say: “The agent asks pnpm to install the package. The SSS shim extracts the exact request and checks
the Exasol evidence before pnpm starts.”

Pause on `SSS BLOCK`, scores `100 / 95 / 75`, exit `23`, and “Installation was not started.”

Validation rule: the protected command exits `23`; one attempt records `child_started=false`; the
canary remains zero; no `node_modules` directory appears.

## 0:52–1:23 — Human intervention

Switch to **OPERATOR**. Press `i` to show ordered evidence, then `a` to allow once.

Say: “The human sees 46 verified model recommendations, the earlier absence and registration 43
minutes later. Allow once creates a signed grant for this package, version, registry, artifact hash,
project, expiry, nonce and policy version. It does not create permanent trust.”

Copy the two displayed values into hidden shell input or a prepared private terminal. Never show the
full token in the recording. Export them as `SSS_APPROVAL_TOKEN` and `SSS_APPROVAL_NONCE`.

Validation rule: approval expiry is five minutes; the signing key remains outside the agent; no
scope field differs from the blocked request.

## 1:23–1:50 — Exact authorized retry

In **AGENT**, retry the identical command with the two values passed only for this container run:

```bash
docker compose -f infra/docker/demo.compose.yaml run --rm \
  -e SSS_APPROVAL_TOKEN -e SSS_APPROVAL_NONCE protected-agent
```

Say: “The retry recomputes the same request identifier and atomically consumes the one use grant.
SSS removes the approval token from the child environment, then starts pnpm once. A second retry or
any changed field blocks.”

Pause on `SSS APPROVAL — exact one-time approval consumed.` and the successful agent completion.

Validation rule: the synthetic lifecycle increments the harmless canary from zero to one; approval
remaining uses is zero; a second retry with the same values exits `23` and does not increment it.

## 1:50–2:16 — Evidence in Exasol

Bring forward the private Radar package detail page. Show the immutable timeline in order: absence,
recurrence, registration transition and blocked attempt. Briefly show collector health and the
policy version.

Say: “Exasol keeps the temporal evidence and durable operational state. Registration never rewrites
the earlier absence. The dashboard explains the decision; it did not enforce it.”

Validation rule: the UI uses authenticated private routes, shows the same origin and timestamps,
and performs no mutation request.

## 2:16–2:40 — Deployment and close

Show the architecture slide or production Compose service list.

Say: “A single organization can self host SSS beside Exasol Personal. The protected agent has no
Docker socket or direct registry route. The gateway forwards only reviewed metadata and artifact
hashes. The complete source, zero cost rehearsal, production runbook and validation gate are in the
repository.”

End on: “SSS gives package installs a memory of what happened before the name became real.”

## Recording acceptance checklist

- Agent install attempt is the first product interaction.
- Block occurs before the package manager and shows exit `23`.
- Operator evidence and exact scope are readable.
- Authorized retry succeeds once; replay fails closed.
- Canary proves zero execution before approval and one execution after approval.
- Radar appears only as supporting evidence.
- No real secrets, public target names or unrelated desktop notifications are visible.
