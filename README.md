# SSS — Stop Slop Squatting

SSS stops autonomous coding agents from installing packages that were previously hallucinated and
later registered by someone else. It stores time ordered evidence in Exasol, applies a deterministic
policy before package manager execution, and sends risky requests to a separate human operator.

## Submission

- **Source code:** this repository
- **Demo video:** [watch the 49-second local agent-protection demo](docs/demo-video/sss-agent-demo.mp4)
- **Pitch deck:** [PowerPoint](docs/pitch/SSS-pitch-deck.pptx) and
  [PDF](docs/pitch/SSS-pitch-deck.pdf)
- **Zero cost rehearsal:** [local agent demo](docs/operations/agent-demo.md)
- **Single organization deployment:** [self hosted operations guide](docs/operations/self-hosted-production.md)

## The two minute story

A coding agent decides to run:

```console
$ pnpm add @sss-demo/reserved-synthetic@1.0.0
SSS BLOCK — @sss-demo/reserved-synthetic@1.0.0
Absence confidence: 100
Target attractiveness: 95
Package policy risk: 75
Reasons: REGISTERED_AFTER_HALLUCINATION, HIGH_GLOBAL_RECURRENCE
Installation was not started.
```

The SSS shim exits `23` before `pnpm` starts. An operator inspects the evidence in another terminal
and either keeps the block or issues a five minute, one use grant scoped to the exact package,
version, registry, artifact hash, project, policy version and request nonce. The same command may be
retried with that grant. Any changed field, expiry or reuse fails closed.

The Radar UI supports the explanation, but the protected agent is the primary demo surface.

## How it works

```text
model probes + public references + opt-in client observations
                           |
                           v
            immutable Exasol evidence and transitions
                           |
coding agent -> package-manager shim -> deterministic Guard
                           |               |
                           |               +-> human intervention and one-use approval
                           v
                exact-permit registry gateway -> approved upstream artifact
```

Only an approved package metadata endpoint returning `404` establishes absence. Authentication
errors, rate limits, server failures, timeouts, DNS/TLS errors and malformed bodies remain
`UNKNOWN`. Historical absence is never rewritten when a package later appears.

The frozen policy is `sss-hackathon-v3`. The fixed synthetic case contains 46 verified model
recommendations across three model configurations, eight distinct client pseudonyms, five public
failed references and 11 observation days. Its pre-execution indices are `100 / 95 / 75`. These
indices are separately labelled scores, not probabilities.

## Supported integrations

The protected image intercepts all supported install entrypoints:

- `pip`, `pip3` and `python -m pip`
- `uv` and Poetry manifests
- `npm`, `pnpm`, Yarn and `npx`

SSS protects any local agent that runs inside the supplied protected container or uses these shims
with immutable real executable mappings. The strongest guarantee applies to an unprivileged SSS
container with no Docker socket and no direct public registry route. Installing the CLI on an
otherwise privileged host cannot stop an agent from bypassing it.

## Quick local validation

Requirements: Linux, Python 3.12, `uv`, Node 22+, pnpm 10.31 and Docker Engine with Compose v2.

```bash
uv sync --frozen --all-groups
pnpm install --frozen-lockfile
./scripts/validate_local.sh
```

This runs Python tests, holdout integrity checks, strict typing and linting, frontend tests and build,
and Python package creation.

For the complete terminal rehearsal, follow
[`docs/operations/agent-demo.md`](docs/operations/agent-demo.md). It uses Exasol Docker Edition and
a private local npm origin, creates no AWS or Azure resources, and costs nothing beyond the machine
already running Docker.

## Connect an agent

Production clients use a scoped token file rather than a token in shell history:

```bash
sss configure \
  --server https://sss.example.com:8443 \
  --token-file secrets/agent_api_token \
  --organization single-org \
  --project my-project

sss protect -- codex
```

The protected session receives only the agent check credential. Approval signing material and
operator credentials remain outside the agent boundary. See the self hosted guide for image,
gateway and network configuration.

## Exasol deployment

The production target is Exasol Personal connected to the single organization Compose profile.
Exasol Personal is free to use, but AWS and Azure infrastructure are billed by their providers. The
zero cost Linux qualification path uses Exasol's official 10 GiB limited Docker Edition as the SQL
runtime. Do not start cloud resources for this rehearsal.

```bash
cp .env.production.example .env.production
# create the documented mode-0600 secret files and set the external Exasol DSN
docker compose --env-file .env.production \
  -f infra/docker/production.compose.yaml config --quiet
docker compose --env-file .env.production \
  -f infra/docker/production.compose.yaml up -d api worker gateway web proxy
uv run python scripts/production_readiness.py \
  --base-url https://sss.example.com:8443 \
  --operator-user operator \
  --credentials-file secrets/api_credentials.json \
  --ca-file secrets/tls_certificate.pem
```

Only the TLS proxy publishes a host port. Exasol stays external. The demo registry, fixtures and
canary never enter the production profile. Full setup, backup, restore and rollback instructions are
in [`docs/operations/self-hosted-production.md`](docs/operations/self-hosted-production.md).

## Repository map

| Path | Purpose |
| --- | --- |
| `packages/core/sss_core` | domain types, extraction, evidence, policy, approvals and Exasol repositories |
| `apps/worker` | scheduled model, public source and transition collectors |
| `apps/api` | authenticated Guard, Radar, intervention and approval API |
| `apps/cli` | agent launcher, shims and operator workflow |
| `apps/gateway` | fail closed PyPI/npm metadata and artifact gateway |
| `apps/web` | authenticated private Radar and evidence UI |
| `infra/exasol` | ordered migrations, analytical views and readiness definitions |
| `infra/docker` | zero cost demo and production Compose profiles |
| `demo` | synthetic package, deterministic agent and harmless canary |
| `tests` | unit, integration, security, E2E and live Exasol coverage |

## Security and privacy boundaries

- Raw absent package names remain private intelligence. Public routes expose aggregates and
  explicitly synthetic identities only.
- Client telemetry is opt in and rejects prompts, code, environment variables, usernames, paths and
  repository names.
- Unknown evidence blocks strict noninteractive agents.
- Direct URLs, VCS sources, alternate registries, shell syntax and unpinned versions fail closed.
- Unknown gateway paths, query strings, origins and artifact hashes never reach an upstream.
- Production uses digest backed scoped credentials, secret files, read only roots, dropped Linux
  capabilities, TLS and Basic authentication at the edge.
- SSS never dynamically executes unknown public artifacts during collection.

See [`SECURITY.md`](SECURITY.md) for reporting and operational assumptions.

## Reproducible release gate

```bash
./scripts/validate_production.sh
```

The driver checks locked installs, Python and frontend suites, live Exasol, the client interception
matrix, production Compose, dependency and secret findings, backup/restore and two protected
rehearsals. It exits nonzero when a required prerequisite or gate is unavailable.

## Contracts and evidence

- [Stable teammate handoff](docs/contracts/teammate-1-handoff.md)
- [OpenAPI components and examples](docs/contracts/openapi-components.yaml)
- [Contract changelog](docs/contracts/CHANGELOG.md)
- [Measurement method and limitations](docs/measurements/README.md)
- [Architecture](ARCHITECTURE.md) and [technology stack](TECH_STACK.md)

## License

Repository licensing and third party asset notices are recorded in [`LICENSE`](LICENSE) and the
pitch deck README. Exasol itself is governed by Exasol's license and deployment limits; it is not
redistributed by this project.
