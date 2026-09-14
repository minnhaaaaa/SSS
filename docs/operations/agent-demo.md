# Terminal-first coding-agent demonstration

This is the final, zero-cost Linux rehearsal. It uses local Exasol Docker Edition because Exasol
Personal's local database preset is not available on Linux. It does not create AWS or Azure
resources. The only package ever executed is the repository's harmless synthetic fixture, inside
an internal Docker network.

The expected story is:

```text
coding agent -> pnpm shim -> SSS Guard -> BLOCK (exit 23)
                                    \-> operator intervention
pnpm child: not started       protected canary delta: 0
```

## 1. Prepare locked dependencies

From the repository root on branch `codex/agent-guard-demo`:

```bash
uv sync --frozen --all-groups
pnpm install --frozen-lockfile
./scripts/validate_local.sh
```

Validation rule: Python tests, holdout checks, strict mypy, Ruff, Node tests, Node type checks, the
web production build and the Python build all exit zero. Do not continue after a failed check.

## 2. Start and load local Exasol

```bash
docker compose -f infra/docker/exasol.compose.yml up -d
export SSS_EXASOL_DSN=127.0.0.1:8563
export SSS_EXASOL_USER=sys
export SSS_EXASOL_PASSWORD=exasol
export SSS_EXASOL_SCHEMA=SSS
./scripts/demo.sh exasol
.venv/bin/python scripts/smoke_exasol.py --expect-demo
```

Initial SQL readiness can take about one minute. If it is not ready, inspect `docker logs
sss-exasol` and retry the final two commands.

Validation rule: readiness is true; migrations are ordered; the recurrence tuple is exactly
`46/3/8/5/11`; status is `registered_after_absence`; and the absence and registration records use
the same origin, `https://npm.demo.sss.test`.

## 3. Build the two local images

```bash
docker build -f infra/docker/python-service.Dockerfile \
  --build-arg SSS_PYTHON_BASE_IMAGE=python:3.12.14-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 \
  --build-arg SSS_UV_VERSION=0.12.13 \
  -t sss-api:local .

docker build -f infra/docker/agent.Dockerfile \
  --build-arg SSS_NODE_BASE_IMAGE=node:22.23.2-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5 \
  --build-arg SSS_PYTHON_BASE_IMAGE=python:3.12.14-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 \
  --build-arg SSS_UV_VERSION=0.12.13 \
  --build-arg SSS_NPM_VERSION=12.0.2 \
  --build-arg SSS_PNPM_VERSION=12.4.1 \
  --build-arg SSS_POETRY_VERSION=2.4.3 \
  -t sss-agent:local .

docker run --rm --network none --user 65532:65532 \
  --entrypoint /usr/local/bin/pnpm sss-agent:local --version
```

Validation rule: both builds exit zero and the networkless version check prints `12.4.1`. That
last check proves the real pnpm executable is already in the image and will not fetch Corepack
metadata from the public internet.

## 4. Start the isolated demo services

```bash
./scripts/generate_demo_tls.sh
export SSS_API_BEARER_TOKENS=demo-agent-token
export SSS_AGENT_API_TOKEN=demo-agent-token
export SSS_APPROVAL_SIGNING_KEY=demo-only-signing-key-not-for-production
export SSS_CANARY_TOKEN=demo-canary-token

docker compose -f infra/docker/demo.compose.yaml up -d \
  api canary registry registry-tls
docker compose -f infra/docker/demo.compose.yaml ps
```

These fixed credentials are scoped to localhost demo containers and are not production secrets.

Validation rule: API becomes healthy; the protected network is internal; the coding-agent service
has no Docker socket, Exasol credentials, canary token, or approval-signing key.

## 5. Seed the controlled registry

```bash
docker compose -f infra/docker/demo.compose.yaml run --rm registry-seed
docker compose -f infra/docker/demo.compose.yaml run --rm registry-seed
```

Validation rule: the first run publishes exactly `@sss-demo/reserved-synthetic@1.0.0`; the second
reports that it is already present. The seed refuses any registry other than
`https://npm.demo.sss.test`.

## 6. Optional narrated baseline

Reset the harmless canary, then demonstrate what happens without Guard:

```bash
docker exec sss-agent-guard-demo-canary-1 /opt/sss/.venv/bin/python -c \
  "import httpx; print(httpx.post('http://127.0.0.1:8090/v1/reset', headers={'Authorization':'Bearer demo-canary-token'}).json())"
docker compose -f infra/docker/demo.compose.yaml run --rm unprotected-agent
docker exec sss-agent-guard-demo-canary-1 /opt/sss/.venv/bin/python -c \
  "import httpx; print(httpx.get('http://127.0.0.1:8090/v1/count', headers={'Authorization':'Bearer demo-canary-token'}).json())"
```

Validation rule: reset reports `0`; the isolated unprotected install runs the synthetic lifecycle;
the next count is exactly `1`. Never run an unprotected install against a public package.

## 7. Run the protected coding agent

Open the operator watcher first in another terminal:

```bash
SSS_API_URL=http://127.0.0.1:8000 \
SSS_API_TOKEN=demo-agent-token \
.venv/bin/sss intervene --watch
```

Then run the coding agent:

```bash
set +e
docker compose -f infra/docker/demo.compose.yaml run --rm protected-agent
agent_exit_code=$?
set -e
test "$agent_exit_code" -eq 23
```

The agent must print:

```text
SSS BLOCK — @sss-demo/reserved-synthetic@1.0.0
Absence confidence: 100
Target attractiveness: 95
Package policy risk: 75
Reasons: REGISTERED_AFTER_HALLUCINATION, HIGH_GLOBAL_RECURRENCE
Installation was not started.
```

Validation rule: exit code is `23`; the operator sees the same package, origin and scores; choosing
`i` displays evidence and choosing the default `k` keeps it blocked. The canary count remains `1`
after a narrated baseline, or `0` when the protected path is run directly after reset.

For the final video, choose `a` instead of `k`. The operator prints the short lived
`SSS_APPROVAL_TOKEN` and `SSS_APPROVAL_NONCE`. Copy them privately into the agent terminal and retry
the identical command:

```bash
export SSS_APPROVAL_TOKEN='<operator output>'
export SSS_APPROVAL_NONCE='<operator output>'
docker compose -f infra/docker/demo.compose.yaml run --rm \
  -e SSS_APPROVAL_TOKEN -e SSS_APPROVAL_NONCE protected-agent
```

The retry must print `SSS APPROVAL — exact one-time approval consumed.` The Guard recomputes the
request identifier, consumes the grant atomically and removes both approval values before starting
pnpm. The harmless canary increases once. A second retry with the same values must return `23` and
must not increase the canary again.

The displayed risk remains `75` because it is the frozen pre-execution score. The controlled
lifecycle hook has not yet been ingested as a static finding at decision time; once ingested, the
separate later assessment is `85` and must carry a new data-as-of timestamp.

## 8. Optional authenticated evidence UI

```bash
pnpm web:dev
```

Open `http://127.0.0.1:5173`. Live mode is the default and redirects to **Agent protection
active**. In the self hosted profile Caddy supplies the scoped browser credential after Basic
authentication; the browser then reads authenticated private Radar, package, decision and coverage
routes. The client contains no approval credential and performs no mutation request. Set
`VITE_SSS_USE_PROTOTYPE_DATA=true` only for an explicitly labelled visual prototype rehearsal.

Validation rule: the page shows the frozen identity, `100/95/75`, policy
`sss-hackathon-v3`, transition age `43`, and terminal commands. It must not claim that a protected
package manager started.

## 9. Non-destructive cleanup

```bash
docker compose -f infra/docker/demo.compose.yaml down
docker compose -f infra/docker/exasol.compose.yml stop
```

Validation rule: no demo application container is running. Exasol data and registry volumes remain
available for another rehearsal. Use `down --volumes` only when intentionally deleting local demo
state.
