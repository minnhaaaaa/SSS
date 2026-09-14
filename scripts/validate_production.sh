#!/usr/bin/env bash
set -euo pipefail

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

runtime_dir="$repo_root/.runtime/release-validation"
mkdir -p "$runtime_dir"
preview_pid=""

cleanup() {
  if [ -n "$preview_pid" ]; then
    kill "$preview_pid" 2>/dev/null || true
    wait "$preview_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

phase() {
  printf '\n[%s] %s\n' "$1" "$2"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'required command is unavailable: %s\n' "$1" >&2
    exit 1
  fi
}

for command in uv pnpm docker git curl google-chrome; do
  require_command "$command"
done

export SSS_EXASOL_DSN=${SSS_EXASOL_DSN:-127.0.0.1:8563}
export SSS_EXASOL_USER=${SSS_EXASOL_USER:-sys}
export SSS_EXASOL_PASSWORD=${SSS_EXASOL_PASSWORD:-exasol}
export SSS_EXASOL_SCHEMA=${SSS_EXASOL_SCHEMA:-SSS}
export SSS_RUN_DOCKER_TESTS=true
python_image=${SSS_PYTHON_BASE_IMAGE:-python:3.12.14-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254}
node_image=${SSS_NODE_BASE_IMAGE:-node:22.23.2-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5}
go_image=${SSS_GO_BASE_IMAGE:-golang:1.26.6-alpine@sha256:3889b425f035be855a72fb4755265311293b6d414521f0a519d819df32222d83}
alpine_image=${SSS_ALPINE_BASE_IMAGE:-alpine:3.24@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b}

phase 1 "Frozen dependencies"
uv sync --frozen --all-groups
pnpm install --frozen-lockfile

phase 2 "Exasol migrations and fixed evidence"
uv run python scripts/migrate_exasol.py
uv run python scripts/migrate_exasol.py
uv run python scripts/smoke_exasol.py --expect-demo

phase 3 "Python unit, integration, security and E2E suites"
uv run pytest -q
uv run python scripts/generate_holdout.py --check
uv run python scripts/measure_holdout.py --check

phase 4 "Static analysis and package build"
uv run mypy packages/core apps scripts demo/synthetic-package/seed_registry.py
uv run ruff check packages apps scripts tests demo
uv build

phase 5 "Frontend tests, type check and production build"
pnpm test
pnpm typecheck
pnpm web:build

phase 6 "Production composition and interception matrix"
uv run pytest -q \
  tests/security/test_production_compose.py \
  tests/security/test_all_client_non_execution.py \
  tests/security/test_container_configuration.py \
  tests/integration/test_gateway.py

docker build -f infra/docker/python-service.Dockerfile \
  --build-arg SSS_PYTHON_BASE_IMAGE="$python_image" \
  --build-arg SSS_UV_VERSION=0.12.13 \
  -t sss-api:production .
docker build -f infra/docker/agent.Dockerfile \
  --build-arg SSS_NODE_BASE_IMAGE="$node_image" \
  --build-arg SSS_PYTHON_BASE_IMAGE="$python_image" \
  --build-arg SSS_UV_VERSION=0.12.13 \
  --build-arg SSS_NPM_VERSION=12.0.2 \
  --build-arg SSS_PNPM_VERSION=10.31.0 \
  --build-arg SSS_POETRY_VERSION=2.4.3 \
  -t sss-agent:production .
docker build -f infra/docker/web.Dockerfile \
  --build-arg SSS_NODE_BASE_IMAGE="$node_image" \
  --build-arg SSS_GO_BASE_IMAGE="$go_image" \
  --build-arg SSS_ALPINE_BASE_IMAGE="$alpine_image" \
  -t sss-web:production .
docker build -f infra/docker/proxy.Dockerfile \
  --build-arg SSS_GO_BASE_IMAGE="$go_image" \
  --build-arg SSS_ALPINE_BASE_IMAGE="$alpine_image" \
  -t sss-proxy:production .

phase 7 "Desktop and narrow browser smoke"
pnpm --filter @sss/web preview --host 127.0.0.1 --port 4173 \
  >"$runtime_dir/web-preview.log" 2>&1 &
preview_pid=$!
for _attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:4173/ >/dev/null; then
    break
  fi
  sleep 0.2
done
curl -fsS http://127.0.0.1:4173/ >/dev/null
google-chrome --headless --disable-gpu --no-sandbox \
  --virtual-time-budget=3000 \
  --window-size=1440,900 --screenshot="$runtime_dir/ui-desktop.png" \
  http://127.0.0.1:4173/ >/dev/null 2>&1
google-chrome --headless --disable-gpu --no-sandbox \
  --virtual-time-budget=3000 \
  --window-size=390,844 --screenshot="$runtime_dir/ui-narrow.png" \
  http://127.0.0.1:4173/ >/dev/null 2>&1
test -s "$runtime_dir/ui-desktop.png"
test -s "$runtime_dir/ui-narrow.png"
kill "$preview_pid"
wait "$preview_pid" 2>/dev/null || true
preview_pid=""

phase 8 "Dependency, secret and available image findings"
pnpm audit --audit-level high
UV_CACHE_DIR="$runtime_dir/uv-tools" uvx pip-audit --strict

if git grep -nE -- \
  '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}' \
  -- ':!tests/**' ':!docs/**' ':!scripts/validate_production.sh'; then
  printf 'tracked secret material pattern detected\n' >&2
  exit 1
fi
if git ls-files | grep -E '(^|/)(secrets?|\.env)(/|$)' | grep -vE '^\.env(\.production)?\.example$'; then
  printf 'tracked secret or non-example environment file detected\n' >&2
  exit 1
fi

trivy_image=${SSS_TRIVY_IMAGE:-aquasec/trivy@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969}
mkdir -p "$runtime_dir/trivy-cache"
for image in sss-api:production sss-agent:production sss-web:production sss-proxy:production; do
  docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$runtime_dir/trivy-cache:/root/.cache/" \
    "$trivy_image" image --quiet --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 "$image"
done

phase 9 "Backup and restore contract"
uv run pytest -q tests/integration/test_backup_restore.py

phase 10 "Two protected agent rehearsals"
for rehearsal in 1 2; do
  printf 'protected rehearsal %s/2\n' "$rehearsal"
  uv run pytest -q tests/e2e/test_agent_guard_demo.py
done

phase 11 "Repository release hygiene"
git diff --check
test "$(git grep -o 'DEMO_VIDEO_URL' -- README.md | wc -l)" -eq 1
test -s docs/pitch/SSS-pitch-deck.pptx
test -s docs/pitch/SSS-pitch-deck.pdf
test -s docs/demo-video-script.md

printf '\nProduction release validation passed.\n'
