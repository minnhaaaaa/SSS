"""Transactional Exasol observation ingestion."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from sss_core import CandidateStatus, EvidenceProvenance, RegistryStatus
from sss_core.repositories.exasol import ExasolConnection
from sss_core.repositories.operations import OperationalRepository

from sss_api.idempotency import idempotency_request_hash
from sss_api.schemas.observations import (
    ClientObservationRequest,
    ModelObservationRequest,
    PublicObservationRequest,
    RegistryObservationRequest,
)


class ExasolObservationRepository:
    def __init__(
        self, connection: ExasolConnection, operational: OperationalRepository
    ) -> None:
        self._connection = connection
        self._operational = operational

    def record(self, kind: str, payload: object, idempotency_key: str) -> str:
        if kind not in {"model", "client", "public", "registry"}:
            raise ValueError("unsupported observation kind")
        typed = cast(
            ModelObservationRequest
            | ClientObservationRequest
            | PublicObservationRequest
            | RegistryObservationRequest,
            payload,
        )
        identifier = (
            typed.check_id
            if isinstance(typed, RegistryObservationRequest)
            else typed.observation_id
        )
        request_hash = idempotency_request_hash(typed.model_dump(mode="json"))
        claim = self._operational.claim_idempotency(
            f"observation:{kind}:{idempotency_key}", request_hash, identifier
        )
        identifier = claim.response_reference
        package = typed.package.canonical()
        common: dict[str, object] = {
            "identifier": identifier,
            "ecosystem": package.ecosystem.value,
            "origin": package.registry_origin,
            "name": package.canonical_name,
        }
        try:
            self._ensure_candidate(common)
            if kind == "model":
                self._record_model(cast(ModelObservationRequest, typed), common)
            elif kind == "client":
                self._record_client(cast(ClientObservationRequest, typed), common)
            elif kind == "public":
                self._record_public(cast(PublicObservationRequest, typed), common)
            else:
                self._record_registry(cast(RegistryObservationRequest, typed), common)
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        return identifier

    def _ensure_candidate(self, values: dict[str, object]) -> None:
        self._connection.execute(
            "MERGE INTO CANDIDATES C USING (SELECT {ecosystem} ECOSYSTEM, {origin} "
            "REGISTRY_ORIGIN, {name} CANONICAL_NAME FROM DUAL) S ON "
            "C.ECOSYSTEM=S.ECOSYSTEM AND C.REGISTRY_ORIGIN=S.REGISTRY_ORIGIN AND "
            "C.CANONICAL_NAME=S.CANONICAL_NAME WHEN NOT MATCHED THEN INSERT "
            "(ECOSYSTEM, REGISTRY_ORIGIN, CANONICAL_NAME, STATUS, DISCLOSURE_CLASS, "
            "SYNTHETIC) VALUES ({ecosystem}, {origin}, {name}, {status}, "
            "'restricted_target_intelligence', FALSE)",
            {**values, "status": CandidateStatus.AMBIGUOUS.value},
        )

    def _record_model(
        self, payload: ModelObservationRequest, values: dict[str, object]
    ) -> None:
        params = {
            **values,
            "provenance": EvidenceProvenance.MODEL_PROBE.value,
            "source_id": payload.source_id,
            "configuration": payload.model_configuration_id,
            "observed_at": _timestamp(payload.observed_at),
            "context_kind": payload.context_kind,
            "explicit": payload.explicit_install_context,
        }
        self._merge_mention(params)

    def _record_client(
        self, payload: ClientObservationRequest, values: dict[str, object]
    ) -> None:
        params = {
            **values,
            "client": payload.client_pseudonym,
            "agent": payload.agent_family,
            "source": payload.requested_source,
            "observed_at": _timestamp(payload.observed_at),
        }
        self._connection.execute(
            "MERGE INTO CLIENT_INSTALL_OBSERVATIONS O USING (SELECT {identifier} "
            "OBSERVATION_ID FROM DUAL) S ON O.OBSERVATION_ID=S.OBSERVATION_ID "
            "WHEN NOT MATCHED THEN INSERT (OBSERVATION_ID, ECOSYSTEM, REGISTRY_ORIGIN, "
            "CANONICAL_NAME, CLIENT_PSEUDONYM, AGENT_FAMILY, REQUESTED_SOURCE, OBSERVED_AT) "
            "VALUES ({identifier}, {ecosystem}, {origin}, {name}, {client}, {agent}, "
            "{source}, {observed_at})",
            params,
        )
        self._merge_mention(
            {
                **values,
                "provenance": EvidenceProvenance.AGENT_INSTALL_ATTEMPT.value,
                "source_id": payload.client_pseudonym,
                "configuration": None,
                "observed_at": _timestamp(payload.observed_at),
                "context_kind": "install",
                "explicit": True,
            }
        )

    def _record_public(
        self, payload: PublicObservationRequest, values: dict[str, object]
    ) -> None:
        params = {
            **values,
            "url_hash": payload.public_url_sha256,
            "source_kind": payload.source_kind,
            "removal": payload.removal_state,
            "observed_at": _timestamp(payload.observed_at),
        }
        self._connection.execute(
            "MERGE INTO PUBLIC_SOURCE_OBSERVATIONS O USING (SELECT {identifier} "
            "OBSERVATION_ID FROM DUAL) S ON O.OBSERVATION_ID=S.OBSERVATION_ID "
            "WHEN NOT MATCHED THEN INSERT (OBSERVATION_ID, ECOSYSTEM, REGISTRY_ORIGIN, "
            "CANONICAL_NAME, PUBLIC_URL_SHA256, SOURCE_KIND, REMOVAL_STATE, OBSERVED_AT) "
            "VALUES ({identifier}, {ecosystem}, {origin}, {name}, {url_hash}, "
            "{source_kind}, {removal}, {observed_at})",
            params,
        )
        provenance = EvidenceProvenance(payload.source_kind).value
        self._merge_mention(
            {
                **values,
                "provenance": provenance,
                "source_id": payload.public_url_sha256,
                "configuration": None,
                "observed_at": _timestamp(payload.observed_at),
                "context_kind": payload.source_kind,
                "explicit": False,
            }
        )

    def _record_registry(
        self, payload: RegistryObservationRequest, values: dict[str, object]
    ) -> None:
        params = {
            **values,
            "endpoint": payload.endpoint,
            "status": payload.status.value,
            "http_status": payload.http_status,
            "checked_at": _timestamp(payload.checked_at),
            "response_hash": payload.response_sha256,
            "error_class": payload.error_class,
        }
        self._connection.execute(
            "MERGE INTO REGISTRY_CHECKS R USING (SELECT {identifier} CHECK_ID FROM DUAL) S "
            "ON R.CHECK_ID=S.CHECK_ID WHEN NOT MATCHED THEN INSERT (CHECK_ID, ECOSYSTEM, "
            "REGISTRY_ORIGIN, CANONICAL_NAME, ENDPOINT, STATUS, HTTP_STATUS, CHECKED_AT, "
            "RESPONSE_SHA256, ERROR_CLASS) VALUES ({identifier}, {ecosystem}, {origin}, "
            "{name}, {endpoint}, {status}, {http_status}, {checked_at}, {response_hash}, "
            "{error_class})",
            params,
        )
        if payload.status is RegistryStatus.ABSENT:
            candidate_status = CandidateStatus.VERIFIED_ABSENT.value
            registration_at = None
            absence_at = _timestamp(payload.checked_at)
        elif payload.status is RegistryStatus.REGISTERED:
            candidate_status = CandidateStatus.REGISTERED.value
            registration_at = _timestamp(payload.checked_at)
            absence_at = None
        else:
            return
        self._connection.execute(
            "UPDATE CANDIDATES SET STATUS=CASE WHEN {status}='registered' AND "
            "FIRST_ABSENCE_AT IS NOT NULL THEN 'registered_after_absence' ELSE "
            "{candidate_status} END, FIRST_ABSENCE_AT=COALESCE(FIRST_ABSENCE_AT, "
            "{absence_at}), FIRST_REGISTRATION_AT=COALESCE(FIRST_REGISTRATION_AT, "
            "{registration_at}) WHERE ECOSYSTEM={ecosystem} AND "
            "REGISTRY_ORIGIN={origin} AND CANONICAL_NAME={name}",
            {
                **params,
                "candidate_status": candidate_status,
                "absence_at": absence_at,
                "registration_at": registration_at,
            },
        )

    def _merge_mention(self, params: dict[str, object]) -> None:
        self._connection.execute(
            "MERGE INTO PACKAGE_MENTIONS M USING (SELECT {identifier} MENTION_ID FROM DUAL) "
            "S ON M.MENTION_ID=S.MENTION_ID WHEN NOT MATCHED THEN INSERT (MENTION_ID, "
            "ECOSYSTEM, REGISTRY_ORIGIN, CANONICAL_NAME, PROVENANCE, SOURCE_ID, "
            "MODEL_CONFIGURATION_ID, OBSERVED_AT, CONTEXT_KIND, CONFIDENCE, "
            "EXPLICIT_CONTEXT) VALUES ({identifier}, {ecosystem}, {origin}, {name}, "
            "{provenance}, {source_id}, {configuration}, {observed_at}, {context_kind}, "
            "1, {explicit})",
            params,
        )


def _timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)
