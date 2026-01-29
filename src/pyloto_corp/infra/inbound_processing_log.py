"""Registro persistente do processamento inbound (rastro auditável)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class InboundProcessingRecord:
    """Dados mínimos do rastro inbound."""

    inbound_event_id: str
    correlation_id: str | None
    task_name: str | None
    started_at: datetime
    finished_at: datetime | None
    enqueued_outbound: bool | None
    error: str | None


class InboundProcessingLogStore:
    """Contrato simples para registrar início/fim do processamento inbound."""

    def mark_started(
        self, inbound_event_id: str, correlation_id: str | None, task_name: str | None
    ) -> None:
        raise NotImplementedError

    def mark_finished(
        self,
        inbound_event_id: str,
        *,
        correlation_id: str | None,
        task_name: str | None,
        enqueued_outbound: bool,
        error: str | None = None,
    ) -> None:
        raise NotImplementedError


class MemoryInboundProcessingLogStore(InboundProcessingLogStore):
    """Store em memória (apenas dev/testes)."""

    def __init__(self, ttl_seconds: int = 604800) -> None:
        self._ttl_seconds = ttl_seconds
        self._data: dict[str, tuple[InboundProcessingRecord, float]] = {}

    def mark_started(
        self, inbound_event_id: str, correlation_id: str | None, task_name: str | None
    ) -> None:
        self._cleanup()
        record = InboundProcessingRecord(
            inbound_event_id=inbound_event_id,
            correlation_id=correlation_id,
            task_name=task_name,
            started_at=datetime.now(tz=UTC),
            finished_at=None,
            enqueued_outbound=None,
            error=None,
        )
        self._data[inbound_event_id] = (record, record.started_at.timestamp())

    def mark_finished(
        self,
        inbound_event_id: str,
        *,
        correlation_id: str | None,
        task_name: str | None,
        enqueued_outbound: bool,
        error: str | None = None,
    ) -> None:
        self._cleanup()
        started, _ = self._data.get(
            inbound_event_id,
            (
                InboundProcessingRecord(
                    inbound_event_id,
                    correlation_id,
                    task_name,
                    datetime.now(tz=UTC),
                    None,
                    None,
                    None,
                ),
                datetime.now(tz=UTC).timestamp(),
            ),
        )
        finished = started
        finished.finished_at = datetime.now(tz=UTC)
        finished.enqueued_outbound = enqueued_outbound
        finished.error = error
        self._data[inbound_event_id] = (finished, finished.finished_at.timestamp())

    def _cleanup(self) -> None:
        now = datetime.now(tz=UTC).timestamp()
        expired = [k for k, (_, ts) in self._data.items() if now - ts > self._ttl_seconds]
        for key in expired:
            del self._data[key]


class RedisInboundProcessingLogStore(InboundProcessingLogStore):
    """Store baseado em Redis com TTL."""

    def __init__(
        self, redis_client: Any, *, ttl_seconds: int = 604800, key_prefix: str = "inbound:log:"
    ) -> None:
        self._redis = redis_client
        self._ttl = ttl_seconds
        self._prefix = key_prefix

    def _key(self, inbound_event_id: str) -> str:
        return f"{self._prefix}{inbound_event_id}"

    def mark_started(
        self, inbound_event_id: str, correlation_id: str | None, task_name: str | None
    ) -> None:
        payload = {
            "inbound_event_id": inbound_event_id,
            "correlation_id": correlation_id,
            "task_name": task_name,
            "started_at": datetime.now(tz=UTC).isoformat(),
            "finished_at": None,
            "enqueued_outbound": None,
            "error": None,
        }
        self._redis.set(self._key(inbound_event_id), json.dumps(payload), ex=self._ttl)

    def mark_finished(
        self,
        inbound_event_id: str,
        *,
        correlation_id: str | None,
        task_name: str | None,
        enqueued_outbound: bool,
        error: str | None = None,
    ) -> None:
        key = self._key(inbound_event_id)
        existing_raw = self._redis.get(key)
        if existing_raw and isinstance(existing_raw, bytes):
            existing_raw = existing_raw.decode("utf-8")
        base: Mapping[str, Any] = json.loads(existing_raw) if existing_raw else {}
        payload = {
            **base,
            "inbound_event_id": inbound_event_id,
            "correlation_id": correlation_id or base.get("correlation_id"),
            "task_name": task_name or base.get("task_name"),
            "started_at": base.get("started_at") or datetime.now(tz=UTC).isoformat(),
            "finished_at": datetime.now(tz=UTC).isoformat(),
            "enqueued_outbound": enqueued_outbound,
            "error": error,
        }
        self._redis.set(key, json.dumps(payload), ex=self._ttl)


class FirestoreInboundProcessingLogStore(InboundProcessingLogStore):
    """Store usando Firestore com TTL por campo expires_at."""

    def __init__(
        self,
        firestore_client: Any,
        *,
        collection: str = "inbound_processing_logs",
        ttl_seconds: int = 604800,
    ) -> None:
        self._client = firestore_client
        self._collection = collection
        self._ttl_seconds = ttl_seconds

    def mark_started(
        self, inbound_event_id: str, correlation_id: str | None, task_name: str | None
    ) -> None:
        expires_at = datetime.now(tz=UTC) + timedelta(seconds=self._ttl_seconds)
        doc = {
            "inbound_event_id": inbound_event_id,
            "correlation_id": correlation_id,
            "task_name": task_name,
            "started_at": datetime.now(tz=UTC),
            "finished_at": None,
            "enqueued_outbound": None,
            "error": None,
            "expires_at": expires_at,
        }
        self._client.collection(self._collection).document(inbound_event_id).set(doc)

    def mark_finished(
        self,
        inbound_event_id: str,
        *,
        correlation_id: str | None,
        task_name: str | None,
        enqueued_outbound: bool,
        error: str | None = None,
    ) -> None:
        doc_ref = self._client.collection(self._collection).document(inbound_event_id)
        doc_ref.set(
            {
                "correlation_id": correlation_id,
                "task_name": task_name,
                "finished_at": datetime.now(tz=UTC),
                "enqueued_outbound": enqueued_outbound,
                "error": error,
            },
            merge=True,
        )


def create_inbound_log_store(
    settings: Any, redis_client: Any = None, firestore_client: Any = None
) -> InboundProcessingLogStore:
    """Factory simples baseada no ambiente."""
    backend = getattr(settings, "inbound_log_backend", "memory").lower()
    ttl = getattr(settings, "inbound_log_ttl_seconds", 604800)

    if backend == "memory":
        return MemoryInboundProcessingLogStore(ttl_seconds=ttl)

    if backend == "redis":
        if not redis_client:
            raise ValueError("Inbound log backend redis requer redis_client")
        return RedisInboundProcessingLogStore(redis_client, ttl_seconds=ttl)

    if backend == "firestore":
        if not firestore_client:
            raise ValueError("Inbound log backend firestore requer firestore_client")
        return FirestoreInboundProcessingLogStore(firestore_client, ttl_seconds=ttl)

    raise ValueError(f"Backend de inbound log desconhecido: {backend}")
