#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose_file="$repo_root/infra/docker/demo.compose.yaml"

export SSS_API_BEARER_TOKENS=demo-agent-token
export SSS_AGENT_API_TOKEN=demo-agent-token
export SSS_APPROVAL_SIGNING_KEY=demo-only-signing-key-not-for-production
export SSS_CANARY_TOKEN=demo-canary-token
export SSS_EXASOL_PASSWORD=${SSS_EXASOL_PASSWORD:-exasol}
unset SSS_APPROVAL_TOKEN SSS_APPROVAL_NONCE

compose() {
    docker compose --progress quiet -f "$compose_file" "$@"
}

canary_count() {
    docker exec sss-agent-guard-demo-canary-1 /opt/sss/.venv/bin/python -c \
        "import httpx; print(httpx.get('http://127.0.0.1:8090/v1/count', headers={'Authorization':'Bearer demo-canary-token'}).json()['count'])"
}

printf '\033[2J\033[H'
printf '%s\n' 'SSS — Stop Slop Squatting'
printf '%s\n\n' 'One command demonstrates block, human approval, execution, and replay protection.'
printf '%s\n' '[setup] Resetting only disposable demo containers and fixture volumes...'
compose down -v --remove-orphans >/dev/null 2>&1
compose up -d api canary registry registry-tls >/dev/null 2>&1
compose run --rm registry-seed >/dev/null 2>&1
printf '%s\n\n' '[setup] Local Exasol evidence, registry, API, and canary are ready.'

printf '%s\n' '[1/4] A coding agent asks pnpm to install a suspicious package.'
set +e
compose run --rm protected-agent 2>&1
blocked_code=$?
set -e
blocked_canary=$(canary_count)
printf 'Blocked exit code: %s | Canary executions: %s\n\n' "$blocked_code" "$blocked_canary"

printf '%s\n' '[2/4] A human inspects the evidence and allows this exact request once.'
operator_output=$(printf 'i\na\n' | \
    SSS_API_URL=http://127.0.0.1:8000 \
    SSS_API_TOKEN=demo-agent-token \
    "$repo_root/.venv/bin/sss" intervene)
printf '%s\n' "$operator_output" | \
    sed -E 's/^(SSS_APPROVAL_(TOKEN|NONCE))=.*/\1=[hidden]/'
approval_token=$(printf '%s\n' "$operator_output" | sed -n 's/^SSS_APPROVAL_TOKEN=//p')
approval_nonce=$(printf '%s\n' "$operator_output" | sed -n 's/^SSS_APPROVAL_NONCE=//p')
test -n "$approval_token"
test -n "$approval_nonce"
export SSS_APPROVAL_TOKEN=$approval_token
export SSS_APPROVAL_NONCE=$approval_nonce
printf '\n'

printf '%s\n' '[3/4] The agent retries. The one-time approval is consumed before pnpm starts.'
set +e
compose run --rm \
    -e SSS_APPROVAL_TOKEN \
    -e SSS_APPROVAL_NONCE \
    -e SSS_DEMO_CANARY_URL=http://canary:8090/v1/events \
    -e SSS_CANARY_TOKEN \
    protected-agent 2>&1
approved_code=$?
set -e
approved_canary=$(canary_count)
printf 'Approved exit code: %s | Canary executions: %s\n\n' "$approved_code" "$approved_canary"

printf '%s\n' '[4/4] The same approval is replayed. SSS fails closed.'
set +e
compose run --rm \
    -e SSS_APPROVAL_TOKEN \
    -e SSS_APPROVAL_NONCE \
    -e SSS_DEMO_CANARY_URL=http://canary:8090/v1/events \
    -e SSS_CANARY_TOKEN \
    protected-agent 2>&1
replay_code=$?
set -e
replay_canary=$(canary_count)
printf 'Replay exit code: %s | Canary executions: %s\n\n' "$replay_code" "$replay_canary"

test "$blocked_code" -eq 23
test "$blocked_canary" -eq 0
test "$approved_code" -eq 0
test "$approved_canary" -eq 1
test "$replay_code" -eq 23
test "$replay_canary" -eq 1

printf '%s\n' 'DEMO PASSED: unsafe by default, human-controlled, exact-scope, and single-use.'
