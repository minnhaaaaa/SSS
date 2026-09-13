#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
venv_bin="$repo_root/.venv/bin"
token=${SSS_API_TOKEN:-sss-local-demo-token}
api_url=${SSS_API_URL:-http://127.0.0.1:8000}

export SSS_ENV=demo
export SSS_API_URL="$api_url"
export SSS_API_TOKEN="$token"
export SSS_API_BEARER_TOKENS="$token"
export SSS_GATEWAY_URL=${SSS_GATEWAY_URL:-http://127.0.0.1:8080}
export SSS_NPM_REGISTRY_URL=https://npm.demo.sss.test
export SSS_PROJECT_ID=project-demo
export SSS_AGENT_FAMILY=codex
export SSS_DEMO_ARTIFACT_SHA256=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
export SSS_APPROVAL_SIGNING_KEY=${SSS_APPROVAL_SIGNING_KEY:-demo-only-signing-key-not-for-production}

case "${1:-help}" in
  api)
    exec "$venv_bin/uvicorn" --factory sss_api.main:create_app --host 127.0.0.1 --port 8000
    ;;
  operator)
    exec "$venv_bin/sss" intervene --watch
    ;;
  agent)
    real_pnpm=$(command -v pnpm)
    export SSS_REAL_EXECUTABLES_JSON="{\"pnpm\":\"$real_pnpm\"}"
    export PATH="$repo_root/apps/cli/sss_cli/shims:$venv_bin:$PATH"
    exec "$venv_bin/sss-demo-agent"
    ;;
  exasol)
    "$venv_bin/python" "$repo_root/scripts/migrate_exasol.py"
    "$venv_bin/python" "$repo_root/scripts/replay_exasol.py" --reset
    exec "$venv_bin/python" "$repo_root/scripts/register_exasol_demo.py"
    ;;
  verify)
    exec "$venv_bin/pytest" "$repo_root/tests/e2e/test_agent_guard_demo.py" -v
    ;;
  *)
    printf '%s\n' "Usage: scripts/demo.sh {exasol|api|operator|agent|verify}"
    ;;
esac
