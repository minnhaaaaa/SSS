"""Create one demo-only Verdaccio user and publish the controlled package."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote

import httpx

PACKAGE = "@sss-demo/reserved-synthetic"
VERSION = "1.0.0"
CERTIFICATE = "/run/sss-tls/npm.demo.sss.test.crt"


def main() -> None:
    registry = os.environ.get("SSS_NPM_REGISTRY_URL", "https://npm.demo.sss.test").rstrip("/")
    if registry != "https://npm.demo.sss.test":
        raise ValueError("seed refuses to publish outside the controlled demo registry")
    encoded_package = quote(PACKAGE, safe="")
    with httpx.Client(verify=CERTIFICATE, timeout=5, trust_env=False) as client:
        if client.get(f"{registry}/{encoded_package}/{VERSION}").status_code == 200:
            print(f"{PACKAGE}@{VERSION} is already present in the controlled registry")
            return
        response = client.put(
            f"{registry}/-/user/org.couchdb.user:sss-demo",
            json={
                "name": "sss-demo",
                "password": "demo-only-password",
                "email": "sss-demo@example.invalid",
                "type": "user",
                "roles": [],
            },
        )
        response.raise_for_status()
        token = response.json()["token"]

    with tempfile.TemporaryDirectory(prefix="sss-demo-npm-") as directory:
        npmrc = Path(directory) / "npmrc"
        npmrc.write_text(
            f"@sss-demo:registry={registry}\n//npm.demo.sss.test/:_authToken={token}\n",
            encoding="utf-8",
        )
        npmrc.chmod(0o600)
        environment = {
            **os.environ,
            "NPM_CONFIG_USERCONFIG": str(npmrc),
        }
        subprocess.run(  # noqa: S603 - fixed executable and exact local registry only
            [
                "/usr/local/bin/pnpm",
                "publish",
                "--registry",
                registry,
                "--no-git-checks",
            ],
            check=True,
            cwd=Path(__file__).parent,
            env=environment,
        )


if __name__ == "__main__":
    main()
