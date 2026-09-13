from __future__ import annotations

from datetime import datetime
from typing import Any

from sss_api.services.control_room import ExasolControlRoomService


class ControlRoomConnection:
    def execute(self, sql: str, query_params: Any = None) -> list[tuple[object, ...]]:
        if "FROM V_RADAR_PRIVATE" in sql:
            return [
                (
                    "npm",
                    "https://registry.npmjs.org",
                    "recurring-package",
                    "registered_after_absence",
                    datetime(2026, 9, 1),
                    datetime(2026, 9, 12),
                    35,
                    3,
                    8,
                    5,
                    11,
                    1,
                )
            ]
        if "LEFT JOIN INSTALL_ATTEMPTS" in sql:
            return [
                (
                    "decision-1",
                    "recurring-package",
                    "npm",
                    "block",
                    "sss-hackathon-v3",
                    datetime(2026, 9, 12),
                    '["REGISTERED_AFTER_HALLUCINATION"]',
                    0,
                    1,
                )
            ]
        if "FROM POLICY_DECISIONS ORDER BY" in sql:
            return [
                (
                    "npm",
                    "https://registry.npmjs.org",
                    "recurring-package",
                    "block",
                    75,
                )
            ]
        if "FROM CLIENT_INSTALL_OBSERVATIONS" in sql:
            return [(8, 11)]
        if "COUNT(DISTINCT CASE WHEN PROVENANCE" in sql:
            return [(35, 5, 3)]
        if "SELECT DISTINCT ECOSYSTEM" in sql:
            return [("npm", "https://registry.npmjs.org")]
        if "V_PACKAGE_EVIDENCE_TIMELINE" in sql:
            return [("check-1", "absent", datetime(2026, 9, 1), "npm")]
        raise AssertionError(f"unexpected query: {sql}")

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


def test_control_room_uses_exasol_evidence_and_decisions() -> None:
    service = ExasolControlRoomService(ControlRoomConnection())  # type: ignore[arg-type]

    package = service.package("recurring-package")
    overview = service.overview()

    assert package is not None
    assert package["state"] == "blocked"
    assert package["attractiveness"] == 95
    assert package["policy_risk"] == 75
    assert package["lifecycle"] == ["Registry absence verified"]
    assert overview["active_threats"] == 1
    assert overview["protected_agents"] == 8
    assert overview["verified_recommendations"] == 35
