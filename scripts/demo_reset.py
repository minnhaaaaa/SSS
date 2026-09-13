"""Reset the authenticated local demo controller."""

from __future__ import annotations

from os import environ

import httpx


def main() -> None:
    response = httpx.post(
        f"{environ['SSS_API_URL'].rstrip('/')}/v1/demo/reset",
        headers={
            "Authorization": f"Bearer {environ['SSS_API_TOKEN']}",
            "Idempotency-Key": "demo-reset-script",
        },
        timeout=5,
    )
    response.raise_for_status()
    print(response.json())


if __name__ == "__main__":
    main()
