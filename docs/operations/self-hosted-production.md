# Single-organization self-hosted deployment

This profile runs the SSS API, collectors, exact-permit registry gateway, read-only web client and
TLS proxy on one Docker host. It connects to an external Exasol Personal database. It does not
start the demo registry, canary, fixture controller, or a local Exasol database. Only the TLS proxy
publishes a host port.

Docker separates the protected agent from general outbound access. The API and worker join
`control-egress` to reach external Exasol Personal, and the worker uses it for the approved model
endpoint. Only the gateway joins `gateway-egress` for registry traffic. Restrict these networks at
the host or cloud firewall: allow `control-egress` only to Exasol and the approved model endpoint,
and `gateway-egress` only to frozen registry origins. Compose networks isolate services but do not
provide destination allowlisting.

The zero-cost qualification path is the local Exasol Docker Edition procedure in
[`exasol-personal.md`](exasol-personal.md). Do not start AWS or Azure resources unless the
organization has explicitly accepted the infrastructure cost.

## Prerequisites

- Linux Docker Engine with Compose v2
- an accessible Exasol Personal database and a dedicated SSS schema/user
- DNS and a trusted TLS certificate for the chosen hostname
- an OpenAI-compatible model endpoint approved for the collector
- a reviewed JSONL prompt manifest

Copy the production template and keep the result untracked:

```bash
cp .env.production.example .env.production
mkdir -m 700 -p secrets config backups
```

## Create scoped credentials

Generate four independent random tokens: browser, protected agent, operator CLI and collector.
Store the raw values in `secrets/browser_api_token`, `secrets/agent_api_token`,
`secrets/operator_api_token` and `secrets/collector_api_token`, mode `0600`. Store only their
lowercase SHA-256 digests in `secrets/api_credentials.json`:

```json
{
  "credentials": [
    {"credential_id":"browser","token_sha256":"BROWSER_SHA256","scopes":["radar:read"],"enabled":true},
    {"credential_id":"agent","token_sha256":"AGENT_SHA256","scopes":["agent:check"],"enabled":true},
    {"credential_id":"operator","token_sha256":"OPERATOR_SHA256","scopes":["approval:write","operator:intervene","radar:read"],"enabled":true},
    {"credential_id":"collector","token_sha256":"COLLECTOR_SHA256","scopes":["collector:write"],"enabled":true}
  ]
}
```

Set the file to mode `0600`. Never put raw tokens in this JSON file. Create a random approval
signing key containing at least 32 bytes in `secrets/approval_signing_key`. Put the existing Exasol
and model-provider secrets in their named files. Generate the Caddy password hash without storing
the plaintext password in Compose:

```bash
docker run --rm caddy:2.10.2-alpine caddy hash-password
```

Copy the result to `secrets/operator_password_hash`. Install the TLS certificate and key at the
paths in `.env.production`. Every secret file must be readable only by its owner.

Validation rule: raw tokens do not occur in `api_credentials.json`, all four credential scopes are
present, and the browser credential has only `radar:read`.

## Prepare Exasol and the registry permit set

Load the environment, run ordered migrations twice, and validate readiness:

```bash
set -a
source .env.production
set +a
uv run python scripts/migrate_exasol.py
uv run python scripts/migrate_exasol.py
uv run python scripts/smoke_exasol.py
```

The second migration must report an empty `applied` list. Build
`SSS_GATEWAY_PERMITS_JSON` from the reviewed lockfile and approval set. Each allowed metadata path
maps to `null`; each artifact path maps to the artifact's verified lowercase SHA-256. Include every
approved transitive artifact. Unknown origins, query strings, paths and hashes fail closed before an
upstream request.

## Render and start

```bash
docker compose --env-file .env.production \
  -f infra/docker/production.compose.yaml config --quiet
docker compose --env-file .env.production \
  -f infra/docker/production.compose.yaml build
docker compose --env-file .env.production \
  -f infra/docker/production.compose.yaml up -d api worker gateway web proxy
docker compose --env-file .env.production \
  -f infra/docker/production.compose.yaml ps
```

Validation rule: only `proxy` publishes port `8443`; API reports healthy; no service named Exasol,
demo, canary or registry exists; and application roots are read-only with all Linux capabilities
dropped.

## Readiness and use

Run the aggregate readiness audit from a trusted operator host. For automation, put the Basic-auth
password in a temporary mode-`0600` file; otherwise the command prompts without echo:

```bash
uv run python scripts/production_readiness.py \
  --base-url https://sss.example.com:8443 \
  --operator-user operator \
  --credentials-file secrets/api_credentials.json \
  --ca-file secrets/tls_certificate.pem
```

The JSON result must set every check and `ready` to `true`. The audit verifies TLS/API readiness,
the frozen policy version, live Exasol migration checksums/views, worker freshness, credential scope
coverage and gateway configuration without printing a secret.

Configure an operator CLI using the separate operator token:

```bash
sss configure \
  --server https://sss.example.com:8443 \
  --token-file secrets/operator_api_token \
  --organization single-org \
  --project production-project
sss intervene --watch
```

To open a protected agent shell, enable the optional profile. Its container can reach only the API
and registry gateway on the internal `protected` network:

```bash
docker compose --env-file .env.production \
  -f infra/docker/production.compose.yaml --profile agent run --rm protected-agent
```

All supported package-manager entrypoints are intercepted: `pip`, `pip3`, `python -m pip`, `uv`,
Poetry, npm, pnpm, Yarn and npx. A blocked command exits `23`, prints the intervention identifier,
and does not start the real package manager.

## Backup, restore and rollback

Create a logical backup while the database is healthy:

```bash
uv run python scripts/backup_exasol.py backups/sss-$(date -u +%Y%m%dT%H%M%SZ)
```

The directory contains one export per table and a manifest with UTC time, application version,
migration checksums, row counts, byte counts and SHA-256 hashes. Copy the directory to protected
storage.

Restore only into an empty schema that has already received the same migrations:

```bash
uv run python scripts/restore_exasol.py backups/sss-YYYYMMDDTHHMMSSZ
```

Restore verifies every file before importing and refuses migration drift or any nonempty data table.
`--allow-nonempty` is an explicit break-glass option and should be used only after an independent
backup.

For an application rollback, keep the database migration level unchanged, restore the previous
digest-pinned image values in `.env.production`, render Compose, deploy, and rerun readiness. Never
downgrade the schema by deleting migration records.

## Stop services

```bash
docker compose --env-file .env.production \
  -f infra/docker/production.compose.yaml down
```

This removes application containers and networks. It does not modify the external Exasol Personal
database or the host secret/backup directories.
