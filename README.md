# SSS — Stop Slop Squatting

SSS preserves evidence of package names recommended before they exist, detects later registration,
and makes deterministic install decisions before an autonomous package-manager process starts.

## Local validation

Requirements: Python 3.12, `uv`, Node 22+, and pnpm 10.31.

```bash
./scripts/validate_local.sh
```

## Exasol Personal

Deployed SSS uses Exasol Personal on AWS or Azure. See
[`docs/operations/exasol-personal.md`](docs/operations/exasol-personal.md) for provision, migration,
readiness, smoke, cost, and cleanup instructions. A real database test runs when all
`SSS_EXASOL_*` variables in `.env.example` are set; otherwise only that credential-gated test skips.

## Integration contracts

Teammate 2 should consume [`docs/contracts/teammate-1-handoff.md`](docs/contracts/teammate-1-handoff.md)
and [`docs/contracts/openapi-components.yaml`](docs/contracts/openapi-components.yaml). The fixed
demo intelligence lives in [`demo/fixtures/fixed-intelligence.json`](demo/fixtures/fixed-intelligence.json).
