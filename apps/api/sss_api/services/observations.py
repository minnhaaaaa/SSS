"""Idempotent observation storage boundary."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from threading import RLock
from typing import Protocol

from sss_core.identity import canonicalize_identity
from sss_core.repositories.exasol import ExasolConnection

from sss_api.schemas.observations import ClientObservation, ModelObservation, PublicObservation

type Observation = ModelObservation | PublicObservation | ClientObservation


class ObservationSink(Protocol):
    def store(self, observation: Observation) -> None: ...


class NoopObservationSink:
    def store(self, observation: Observation) -> None:
        del observation


class ExasolObservationSink:
    """Persist normalized observations into the shared Exasol evidence schema."""

    def __init__(self, connection: ExasolConnection) -> None:
        self._connection = connection

    def store(self, observation: Observation) -> None:
        package = canonicalize_identity(
            observation.package.ecosystem,
            observation.package.registry_origin,
            observation.package.canonical_name,
        )
        parameters: dict[str, object] = {
            "observation_id": observation.observation_id,
            "ecosystem": package.ecosystem.value,
            "registry_origin": package.registry_origin,
            "canonical_name": package.canonical_name,
            "provenance": observation.provenance,
            "observed_at": _database_timestamp(observation.observed_at),
            "explicit_context": observation.explicit_install_context,
            "context_kind": (
                "package_install" if observation.explicit_install_context else "package_reference"
            ),
        }
        try:
            self._connection.execute(
                "MERGE INTO CANDIDATES T USING (SELECT {ecosystem} ECOSYSTEM, "
                "{registry_origin} REGISTRY_ORIGIN, {canonical_name} CANONICAL_NAME FROM DUAL) "
                "S ON T.ECOSYSTEM=S.ECOSYSTEM AND T.REGISTRY_ORIGIN=S.REGISTRY_ORIGIN "
                "AND T.CANONICAL_NAME=S.CANONICAL_NAME WHEN NOT MATCHED THEN INSERT "
                "(ECOSYSTEM, REGISTRY_ORIGIN, CANONICAL_NAME, STATUS, FIRST_ABSENCE_AT, "
                "FIRST_REGISTRATION_AT, DISCLOSURE_CLASS, SYNTHETIC) VALUES ({ecosystem}, "
                "{registry_origin}, {canonical_name}, 'ambiguous', NULL, NULL, "
                "'restricted_target_intelligence', FALSE)",
                parameters,
            )
            if isinstance(observation, PublicObservation):
                self._store_public(observation, parameters)
                parameters["source_id"] = hashlib.sha256(observation.source_id.encode()).hexdigest()
                parameters["model_configuration_id"] = None
            elif isinstance(observation, ClientObservation):
                self._store_client(observation, parameters)
                parameters["source_id"] = observation.client_pseudonym
                parameters["model_configuration_id"] = None
            else:
                parameters["source_id"] = observation.source_id
                parameters["model_configuration_id"] = observation.model_configuration_id
            self._connection.execute(
                "MERGE INTO PACKAGE_MENTIONS T USING (SELECT {observation_id} MENTION_ID "
                "FROM DUAL) S ON T.MENTION_ID=S.MENTION_ID WHEN NOT MATCHED THEN INSERT "
                "(MENTION_ID, ECOSYSTEM, REGISTRY_ORIGIN, CANONICAL_NAME, PROVENANCE, "
                "SOURCE_ID, MODEL_CONFIGURATION_ID, OBSERVED_AT, CONTEXT_KIND, CONFIDENCE, "
                "EXPLICIT_CONTEXT) VALUES ({observation_id}, {ecosystem}, {registry_origin}, "
                "{canonical_name}, {provenance}, {source_id}, {model_configuration_id}, "
                "{observed_at}, {context_kind}, 1.0, {explicit_context})",
                parameters,
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    def _store_public(self, observation: PublicObservation, parameters: dict[str, object]) -> None:
        parameters["public_url_sha256"] = hashlib.sha256(observation.source_id.encode()).hexdigest()
        self._connection.execute(
            "MERGE INTO PUBLIC_SOURCE_OBSERVATIONS T USING (SELECT {observation_id} "
            "OBSERVATION_ID FROM DUAL) S ON T.OBSERVATION_ID=S.OBSERVATION_ID "
            "WHEN NOT MATCHED THEN INSERT (OBSERVATION_ID, ECOSYSTEM, REGISTRY_ORIGIN, "
            "CANONICAL_NAME, PUBLIC_URL_SHA256, SOURCE_KIND, REMOVAL_STATE, OBSERVED_AT) "
            "VALUES ({observation_id}, {ecosystem}, {registry_origin}, {canonical_name}, "
            "{public_url_sha256}, {provenance}, 'present', {observed_at})",
            parameters,
        )

    def _store_client(self, observation: ClientObservation, parameters: dict[str, object]) -> None:
        parameters.update(
            client_pseudonym=observation.client_pseudonym,
            agent_family=observation.agent_family,
        )
        self._connection.execute(
            "MERGE INTO CLIENT_INSTALL_OBSERVATIONS T USING (SELECT {observation_id} "
            "OBSERVATION_ID FROM DUAL) S ON T.OBSERVATION_ID=S.OBSERVATION_ID "
            "WHEN NOT MATCHED THEN INSERT (OBSERVATION_ID, ECOSYSTEM, REGISTRY_ORIGIN, "
            "CANONICAL_NAME, CLIENT_PSEUDONYM, AGENT_FAMILY, REQUESTED_SOURCE, OBSERVED_AT) "
            "VALUES ({observation_id}, {ecosystem}, {registry_origin}, {canonical_name}, "
            "{client_pseudonym}, {agent_family}, 'registry', {observed_at})",
            parameters,
        )


class ObservationStore:
    def __init__(self, sink: ObservationSink | None = None) -> None:
        self._sink = sink or NoopObservationSink()
        self._by_key: dict[str, Observation] = {}
        self._lock = RLock()

    async def record(self, idempotency_key: str, observation: Observation) -> Observation:
        with self._lock:
            existing = self._by_key.get(idempotency_key)
            if existing is not None:
                if existing != observation:
                    raise ValueError("idempotency key was already used for another observation")
                return existing
            self._sink.store(observation)
            self._by_key[idempotency_key] = observation
            return observation

    def list_all(self) -> tuple[Observation, ...]:
        """Return the observations actually accepted by this process."""
        with self._lock:
            return tuple(self._by_key.values())


def _database_timestamp(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None)
