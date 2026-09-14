#!/usr/bin/env python3
"""Fail-closed readiness audit for a single-organization deployment."""

from __future__ import annotations

import argparse
import getpass
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sss_core import POLICY_VERSION
from sss_core.auth import CredentialRecord
from sss_core.config import ExasolSettings
from sss_core.repositories.exasol import SchemaReadinessChecker
from sss_gateway.config import GatewaySettings
from sss_gateway.policy import GatewayPermitSet

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SCOPE_GROUPS = (
    frozenset({"agent:check"}),
    frozenset({"radar:read"}),
    frozenset({"approval:write", "operator:intervene"}),
    frozenset({"collector:write"}),
)


def worker_is_fresh(
    outcome: str | None,
    updated_at: datetime | None,
    *,
    now: datetime,
    max_age: int,
) -> bool:
    if outcome != "success" or updated_at is None:
        return False
    timestamp = updated_at if updated_at.tzinfo is not None else updated_at.replace(tzinfo=UTC)
    return 0 <= (now - timestamp.astimezone(UTC)).total_seconds() <= max_age


def _credentials_cover_required_scopes(path: Path) -> bool:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        records = tuple(
            CredentialRecord.from_json(value) for value in document["credentials"]
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False
    enabled = tuple(record.scopes for record in records if record.enabled)
    return all(any(required <= scopes for scopes in enabled) for required in REQUIRED_SCOPE_GROUPS)


def _read_secret(path: Path) -> str:
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError("secret file is empty")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--operator-user", default=os.getenv("SSS_OPERATOR_USERNAME", ""))
    parser.add_argument("--operator-password-file", type=Path)
    parser.add_argument("--credentials-file", type=Path)
    parser.add_argument("--ca-file", type=Path)
    parser.add_argument("--max-worker-age", type=int, default=900)
    args = parser.parse_args()
    if not args.base_url.startswith("https://"):
        raise SystemExit("production readiness requires an HTTPS base URL")
    if not args.operator_user:
        raise SystemExit("operator username is required")
    password = (
        _read_secret(args.operator_password_file)
        if args.operator_password_file
        else getpass.getpass("Operator password: ")
    )
    credentials_path = args.credentials_file or Path(
        os.environ.get("SSS_API_CREDENTIALS_FILE", "")
    )
    checks: dict[str, bool] = {}
    try:
        response = httpx.get(
            f"{args.base_url.rstrip('/')}/health/ready",
            auth=(args.operator_user, password),
            verify=str(args.ca_file) if args.ca_file else True,
            timeout=10,
            trust_env=False,
        )
        payload = response.json()
        checks["tls_api"] = response.status_code == 200 and payload.get("status") == "ready"
        checks["policy"] = payload.get("policy_version") == POLICY_VERSION
    except (httpx.HTTPError, ValueError, json.JSONDecodeError):
        checks["tls_api"] = False
        checks["policy"] = False
    checks["credentials"] = bool(credentials_path) and _credentials_cover_required_scopes(
        credentials_path
    )
    try:
        GatewaySettings.from_env()
        GatewayPermitSet.from_env()
        checks["gateway"] = True
    except ValueError:
        checks["gateway"] = False

    connection = None
    try:
        import pyexasol  # type: ignore[import-untyped]

        settings = ExasolSettings.from_env()
        connection = pyexasol.connect(
            dsn=settings.dsn,
            user=settings.user,
            password=settings.password,
            schema=settings.schema,
            autocommit=False,
        )
        readiness = SchemaReadinessChecker(ROOT / "infra/exasol/migrations").check(connection)
        checks["exasol_schema"] = readiness.ready
        rows = connection.execute(
            "SELECT OUTCOME, UPDATED_AT FROM WORKER_JOBS ORDER BY UPDATED_AT DESC LIMIT 1"
        ).fetchall()
        if rows:
            updated = rows[0][1]
            if isinstance(updated, str):
                updated = datetime.fromisoformat(updated)
            checks["worker_fresh"] = worker_is_fresh(
                str(rows[0][0]),
                updated,
                now=datetime.now(UTC),
                max_age=args.max_worker_age,
            )
        else:
            checks["worker_fresh"] = False
    except Exception:
        checks["exasol_schema"] = False
        checks["worker_fresh"] = False
    finally:
        if connection is not None:
            connection.close()
    report = {"ready": all(checks.values()), "checks": checks}
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report["ready"] else 1)


if __name__ == "__main__":
    main()
