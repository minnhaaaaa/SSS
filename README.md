# SSS — Stop Slop Squatting

SSS preserves evidence of package names recommended before they exist, detects later registration,
and makes deterministic install decisions before an autonomous package-manager process starts.

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

## Integration contracts

Teammate 2 should consume [`docs/contracts/teammate-1-handoff.md`](docs/contracts/teammate-1-handoff.md)
and [`docs/contracts/openapi-components.yaml`](docs/contracts/openapi-components.yaml). The fixed
demo intelligence lives in [`demo/fixtures/fixed-intelligence.json`](demo/fixtures/fixed-intelligence.json).
