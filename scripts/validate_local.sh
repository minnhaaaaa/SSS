#!/usr/bin/env bash
set -euo pipefail

uv sync --frozen --all-groups
uv run pytest -q
uv run python scripts/generate_holdout.py --check
uv run python scripts/measure_holdout.py --check
uv run mypy packages/core apps/worker scripts
uv run ruff check packages apps scripts tests
pnpm install --frozen-lockfile
pnpm test
uv build --offline
