# Exasol deployment and validation

SSS targets **Exasol Personal**, not an in-process database, for deployed integration. DuckDB appears
only in fast SQL compatibility tests. Exasol Personal is free for personal use, but AWS/Azure
infrastructure is billed by the selected provider. The current Personal `local` preset supports only
Apple-silicon macOS. On Linux, use the official Exasol Docker Edition for zero-cost development and
integration testing. Docker Edition is a separate, non-production edition limited to 10 GiB raw data;
do not describe it as Exasol Personal in product claims.

Official references:

- [Quick start with Exasol Personal](https://docs.exasol.com/db/latest/get_started/quick_start_guide.htm)
- [AWS account setup](https://docs.exasol.com/db/latest/get_started/exasol_personal_aws_setup.htm)
- [Azure account setup](https://docs.exasol.com/db/latest/get_started/exasol_personal_azure_setup.htm)
- [Exasol Docker Edition](https://github.com/exasol/docker-db)

As of September 2026, the launcher runs on Linux, macOS and Windows. The `local` Personal database
preset is limited to macOS 15+ on Apple silicon. This repository includes a pinned Docker Edition
profile so Linux contributors can execute the real Exasol migrations and analytical views without a
paid cloud account.

## 1. Validate the local application

```bash
./scripts/validate_local.sh
```

This restores locked dependencies, runs Python and Node tests, strict production mypy, Ruff, and
builds the Python artifacts offline.

## 2. Zero-cost Linux development

Prerequisites: Linux x86-64 with Docker, at least 8 GiB host RAM, and at least 12 GiB free disk. The
container receives 8 GiB RAM, persists `/exa` in a named volume, and exposes SQL only on localhost.
The image is pinned to Exasol `2025.1.14` and an immutable digest; update both deliberately and
re-run the integration suite.

```bash
docker compose -f infra/docker/exasol.compose.yml up -d
cp .env.example .env
set -a
source .env
set +a
uv run python scripts/migrate_exasol.py
uv run python scripts/migrate_exasol.py
uv run python scripts/smoke_exasol.py
uv run python scripts/replay_exasol.py --reset
uv run python scripts/smoke_exasol.py --expect-demo
```

The first migration must report `"ready": true`. The second must additionally report
`"applied": []`. Both smoke checks must report `"ready": true`, and the final one must report the
fixed recurrence tuple `46/3/8/5/11`.

Initial startup and restart can take about one minute. An `UNEXPECTED_EOF_WHILE_READING` TLS error
during that window means the SQL service is not ready yet; do not run migrations until a connection
succeeds. Inspect progress with `docker logs sss-exasol`, then retry the readiness or smoke command.

Stop the database without deleting its data:

```bash
docker compose -f infra/docker/exasol.compose.yml stop
```

Remove the local container and data only when a clean reset is intended:

```bash
docker compose -f infra/docker/exasol.compose.yml down --volumes
```

## 3. Provision Exasol Personal in paid infrastructure

Installing the launcher accepts the Exasol Personal EULA:

```bash
curl https://www.exasol.com/install/ | sh
mkdir -p deployment/exasol-personal
cd deployment/exasol-personal
```

AWS (requires a configured profile and sufficient EC2/IAM quota):

```bash
export AWS_PROFILE=exasol
exasol install aws
```

Azure (location is required):

```bash
az login
exasol install azure --location centralindia
```

The default cloud instance is memory-optimized and incurs cost. If installation is interrupted,
inspect the provider resources immediately; launcher state deletion alone does not delete cloud
resources. Use `exasol stop` to stop compute and `exasol destroy` to remove the deployment when the
demo is finished. Storage/network resources may still cost money while stopped.

## 4. Connect and migrate

Run `exasol info` in the deployment directory and put its database connection values into an
untracked `.env`. Never commit `secrets-exasol-*.json`.

```bash
set -a
source .env
set +a
uv run python scripts/migrate_exasol.py
uv run python scripts/migrate_exasol.py
```

Both commands must report `"ready": true`; the second must report an empty `applied` array. The
readiness check verifies ordered migration checksums and all required analytical views.

## 5. Replay and smoke-test

Teammate 2's demo endpoint and `scripts/replay_exasol.py` call `ExasolDemoRepository.reset()` and
`replay_global_evidence()` using `demo/fixtures/fixed-intelligence.json`. The `--reset` flag deletes
only fixture-scoped rows before replaying global evidence; it never clears unrelated intelligence.
Replay is idempotent only within the replay stage and is disabled after registration in the guided
demo.

Before registration:

```bash
uv run python scripts/smoke_exasol.py
```

After replay (and again after the full live registration transition):

```bash
uv run python scripts/smoke_exasol.py --expect-demo
```

Acceptance: schema ready; recurrence exactly `46/3/8/5/11`; eight distinct client pseudonyms;
historical absence remains; registered transition uses the same registry origin; public views do
not expose the package name.
