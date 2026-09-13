# Exasol Personal deployment and validation

SSS uses **Exasol Personal**, not an in-process database, for deployed integration. DuckDB appears
only in fast SQL compatibility tests. Exasol Personal is free for personal use, but AWS/Azure
infrastructure is billed by the selected provider.

Official references:

- [Quick start with Exasol Personal](https://docs.exasol.com/db/latest/get_started/quick_start_guide.htm)
- [AWS account setup](https://docs.exasol.com/db/latest/get_started/exasol_personal_aws_setup.htm)
- [Azure account setup](https://docs.exasol.com/db/latest/get_started/exasol_personal_azure_setup.htm)

As of September 2026, the launcher runs on Linux, macOS and Windows. The `local` database preset
is limited to macOS 15+ on Apple silicon, so Linux development runs the SSS application locally
against Exasol Personal on AWS or Azure.

## 1. Validate the local application

```bash
./scripts/validate_local.sh
```

This restores locked dependencies, runs Python and Node tests, strict production mypy, Ruff, and
builds the Python artifacts offline.

## 2. Provision Exasol Personal

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

## 3. Connect and migrate

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

## 4. Replay and smoke-test

Teammate 2's demo endpoint calls `ExasolDemoRepository.reset()` and
`replay_global_evidence()` using `demo/fixtures/fixed-intelligence.json`. Replay is idempotent only
within the replay stage and is disabled after registration.

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
