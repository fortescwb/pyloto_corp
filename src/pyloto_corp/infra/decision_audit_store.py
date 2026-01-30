"""Persistência de auditoria para decisões finais (LLM3)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pyloto_corp.domain.protocols.decision_audit_store import DecisionAuditStoreProtocol
from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)


class DecisionAuditStore(DecisionAuditStoreProtocol):
    """Contrato de auditoria."""

    def append(self, record: dict[str, Any]) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class MemoryDecisionAuditStore(DecisionAuditStore):
    """Store em memória (apenas dev/testes)."""

    def __init__(self) -> None:
        self.data: list[dict[str, Any]] = []

    def append(self, record: dict[str, Any]) -> None:
        self.data.append(record)


class FirestoreDecisionAuditStore(DecisionAuditStore):
    """Store em Firestore."""

    def __init__(self, firestore_client: Any, collection: str = "decision_audit") -> None:
        self._client = firestore_client
        self._collection = collection

    def append(self, record: dict[str, Any]) -> None:
        doc_id = (
            record.get("correlation_id")
            or hashlib.sha256(json.dumps(record, sort_keys=True).encode("utf-8")).hexdigest()
        )
        record = {**record, "created_at": datetime.now(tz=UTC)}
        self._client.collection(self._collection).document(doc_id).set(record)


def create_decision_audit_store(
    settings: Any, firestore_client: Any | None = None
) -> DecisionAuditStore:
    """Factory simples baseada no backend."""
    backend = getattr(settings, "decision_audit_backend", "memory").lower()

    if backend == "memory":
        return MemoryDecisionAuditStore()

    if backend == "firestore":
        if firestore_client is None:
            from google.cloud import firestore

            firestore_client = firestore.Client(
                project=settings.firestore_project_id or settings.gcp_project,
                database=settings.firestore_database_id,
            )
        return FirestoreDecisionAuditStore(firestore_client)

    raise ValueError(f"DECISION_AUDIT_BACKEND inválido: {backend}")
