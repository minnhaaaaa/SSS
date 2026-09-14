#!/usr/bin/env bash
set -euo pipefail

uv sync --frozen --all-groups
uv run pytest -q
uv run python scripts/generate_holdout.py --check
uv run python scripts/measure_holdout.py --check
uv run mypy packages/core apps scripts demo/synthetic-package/seed_registry.py
uv run ruff check packages apps scripts tests demo
pnpm install --frozen-lockfile
pnpm test
pnpm typecheck
pnpm web:build
uv build
