"""Replay the authenticated fixed-evidence demo step."""

from __future__ import annotations

from os import environ

import httpx


def main() -> None:
    response = httpx.post(
        f"{environ['SSS_API_URL'].rstrip('/')}/v1/demo/replay",
        headers={
            "Authorization": f"Bearer {environ['SSS_API_TOKEN']}",
            "Idempotency-Key": "demo-replay-script",
        },
        timeout=5,
    )
    response.raise_for_status()
    print(response.json())


if __name__ == "__main__":
    main()
