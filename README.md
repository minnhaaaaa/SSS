# SSS — Stop Slop Squatting

SSS preserves evidence of package names recommended before they exist, detects later registration,
and makes deterministic install decisions before an autonomous package-manager process starts.

## What the final demo shows

The primary surface is a protected coding agent, not a dashboard. The agent delegates
`pnpm add @sss-demo/reserved-synthetic@1.0.0`; SSS intercepts the exact argument vector, reads the
frozen Exasol-backed evidence, exits `23`, and proves that neither pnpm nor package code started. A
separate operator terminal receives the intervention and can inspect, keep blocked, or issue one
exact-scope approval. The browser UI is optional, read-only evidence.

Run the zero-cost Linux rehearsal from
[`docs/operations/agent-demo.md`](docs/operations/agent-demo.md). It uses local Exasol Docker
Edition, an isolated Verdaccio registry, a harmless canary, and no AWS or Azure resources.

## Local validation

Requirements: Python 3.12, `uv`, Node 22+, and pnpm 10.31.

```bash
./scripts/validate_local.sh
```

## Exasol

The target deployment uses Exasol Personal. AWS and Azure infrastructure is billed by the cloud
provider, and Exasol Personal's local preset currently supports only Apple-silicon macOS. Linux
development therefore uses Exasol's official, free, 10 GiB-limited Docker Edition as the local SQL
integration runtime. See [`docs/operations/exasol-personal.md`](docs/operations/exasol-personal.md)
for the zero-cost local workflow, Personal deployment options, migrations, replay, readiness, and
teardown. The credential-gated database test runs whenever `SSS_EXASOL_*` is configured.

Do not run the AWS or Azure Personal presets for this rehearsal: cloud infrastructure is billable.

## Integration contracts

Teammate 2 should consume [`docs/contracts/teammate-1-handoff.md`](docs/contracts/teammate-1-handoff.md)
and [`docs/contracts/openapi-components.yaml`](docs/contracts/openapi-components.yaml). The fixed
demo intelligence lives in [`demo/fixtures/fixed-intelligence.json`](demo/fixtures/fixed-intelligence.json).
