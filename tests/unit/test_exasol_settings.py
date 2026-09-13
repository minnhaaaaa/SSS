from __future__ import annotations

import pytest
from sss_core.config import ExasolSettings


def test_exasol_settings_require_all_personal_connection_values() -> None:
    with pytest.raises(ValueError, match="SSS_EXASOL_PASSWORD"):
        ExasolSettings.from_mapping(
            {
                "SSS_EXASOL_DSN": "db.example.test:8563",
                "SSS_EXASOL_USER": "sys",
                "SSS_EXASOL_SCHEMA": "SSS",
            }
        )


def test_exasol_settings_validate_schema_and_hide_password() -> None:
    settings = ExasolSettings.from_mapping(
        {
            "SSS_EXASOL_DSN": "db.example.test:8563",
            "SSS_EXASOL_USER": "sys",
            "SSS_EXASOL_PASSWORD": "do-not-print-this",
            "SSS_EXASOL_SCHEMA": "SSS_DEMO",
        }
    )

    assert settings.schema == "SSS_DEMO"
    assert "do-not-print-this" not in repr(settings)

    with pytest.raises(ValueError, match="schema"):
        ExasolSettings.from_mapping(
            {
                "SSS_EXASOL_DSN": "db.example.test:8563",
                "SSS_EXASOL_USER": "sys",
                "SSS_EXASOL_PASSWORD": "secret",
                "SSS_EXASOL_SCHEMA": "bad-schema;drop",
            }
        )
