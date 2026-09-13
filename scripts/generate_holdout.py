from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
DATASET = ROOT / "data/holdout/mentions-v1.jsonl"
DIGEST = ROOT / "data/holdout/mentions-v1.sha256"


def _row(
    *,
    example_id: str,
    ecosystem: str,
    client: str,
    text: str,
    canonical_name: str,
    overlap: bool,
) -> dict[str, object]:
    return {
        "example_id": example_id,
        "ecosystem": ecosystem,
        "client": client,
        "text": text,
        "overlap": overlap,
        "teammate_1_label": {
            "include": True,
            "canonical_names": [canonical_name],
        },
        "teammate_2_label": None,
        "corpus_kind": "controlled_deterministic_seed",
    }


def build_holdout() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    python_templates = (
        ("pip", "pip install {name}==1.0"),
        ("pip3", "pip3 install {name}>=1"),
        ("python -m pip", "python -m pip install {name}~=1.2"),
        ("uv", "uv add {name}==2.0"),
        ("uv pip", "uv pip install {name}>=2"),
    )
    npm_templates = (
        ("npm", "npm install {name}@1"),
        ("pnpm", "pnpm add {name}@^2"),
        ("yarn", "yarn add {name}@~3"),
        ("npx", "npx --yes {name}@latest"),
    )
    for index in range(100):
        name = f"sss-pypi-seed-{index:03d}"
        client, template = python_templates[index % len(python_templates)]
        rows.append(
            _row(
                example_id=f"pypi-{index:03d}",
                ecosystem="pypi",
                client=client,
                text=template.format(name=name),
                canonical_name=name,
                overlap=index < 25,
            )
        )
    for index in range(100):
        name = f"sss-npm-seed-{index:03d}"
        client, template = npm_templates[index % len(npm_templates)]
        rows.append(
            _row(
                example_id=f"npm-{index:03d}",
                ecosystem="npm",
                client=client,
                text=template.format(name=name),
                canonical_name=name,
                overlap=index < 25,
            )
        )
    return rows


def render_holdout() -> bytes:
    lines = [json.dumps(row, sort_keys=True, separators=(",", ":")) for row in build_holdout()]
    return ("\n".join(lines) + "\n").encode()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the deterministic extraction seed corpus"
    )
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    content = render_holdout()
    digest = hashlib.sha256(content).hexdigest()
    if arguments.check:
        if not DATASET.exists() or DATASET.read_bytes() != content:
            raise SystemExit("holdout dataset is not reproducible; regenerate it")
        if not DIGEST.exists() or DIGEST.read_text(encoding="utf-8").strip() != digest:
            raise SystemExit("holdout digest does not match generated content")
        return
    DATASET.parent.mkdir(parents=True, exist_ok=True)
    DATASET.write_bytes(content)
    DIGEST.write_text(f"{digest}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
