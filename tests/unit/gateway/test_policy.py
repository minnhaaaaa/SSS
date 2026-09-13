from __future__ import annotations

import pytest
from sss_gateway.policy import GatewayPermitError, GatewayPermitSet


def test_permit_set_loads_exact_metadata_and_artifact_paths() -> None:
    permits = GatewayPermitSet.from_env(
        {
            "SSS_GATEWAY_PERMITS_JSON": (
                '{"npm":{"/safe-lib":null,'
                '"/safe-lib/-/safe-lib-1.0.0.tgz":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
                'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}'
            )
        }
    )

    assert permits.authorize("NPM", "/safe-lib").expected_sha256 is None
    assert (
        permits.authorize("npm", "/safe-lib/-/safe-lib-1.0.0.tgz").expected_sha256
        == "a" * 64
    )


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"SSS_GATEWAY_PERMITS_JSON": "[]"},
        {"SSS_GATEWAY_PERMITS_JSON": '{"npm":{"/pkg":"short"}}'},
        {"SSS_GATEWAY_PERMITS_JSON": '{"npm":{"/../escape":null}}'},
    ],
)
def test_permit_set_rejects_missing_or_unsafe_configuration(values: dict[str, str]) -> None:
    with pytest.raises(GatewayPermitError):
        GatewayPermitSet.from_env(values)
