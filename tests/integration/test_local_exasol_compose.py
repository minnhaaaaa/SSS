from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]


def test_local_exasol_compose_is_pinned_private_and_persistent() -> None:
    compose_path = ROOT / "infra/docker/exasol.compose.yml"
    document = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    service = document["services"]["exasol"]

    assert document["name"] == "sss-local-exasol"
    assert service["image"] == (
        "exasol/docker-db:2025.1.14@"
        "sha256:620b97790dfdab8284f4f38b220c322bdd733dbf1e1bbfb0f1dc0b6904ca8115"
    )
    assert service["privileged"] is True
    assert service["ports"] == ["127.0.0.1:8563:8563"]
    assert service["volumes"] == ["sss_exasol_data:/exa"]
    assert service["mem_limit"] == "8g"
    assert service["stop_grace_period"] == "120s"
    assert document["volumes"] == {"sss_exasol_data": {}}
