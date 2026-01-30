"""Armazenamento de trilha de auditoria em Firestore com encadeamento por hash.

Implementação de AuditLogStore que persiste eventos com integridade:
- Append-only: eventos nunca são modificados ou deletados
- Encadeamento: cada evento referencia hash do anterior (SHA256)
- Transacional: usa Firestore transactions para evitar race conditions
- Concorrência: tolerante a conflitos (retry no app layer)

Conforme regras_e_padroes.md:
- Máximo 200 linhas por arquivo
- Zero-trust: sempre validar prev_hash
- Logs sem PII
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from google.cloud import firestore

from pyloto_corp.domain.audit import AuditEvent, AuditLogStore
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    pass

logger: logging.Logger = get_logger(__name__)


class FirestoreAuditLogStore(AuditLogStore):
    """Armazenamento de auditoria em Firestore com trilha encadeada.

    Schema:
        /conversations/{user_key}/audit/{event_id}
        ├── event_id: str (UUID)
        ├── user_key: str
        ├── tenant_id: str | None
        ├── timestamp: datetime
        ├── actor: str (SYSTEM | HUMAN)
        ├── action: str (USER_CONTACT | EXPORT_GENERATED | ...)
        ├── reason: str
        ├── prev_hash: str | None (hash do evento anterior)
        ├── hash: str (SHA256 do evento)
        └── correlation_id: str | None

    Integridade:
        hash = SHA256(canonical_json(event_sem_hash) + prev_hash)
        Append condicional valida: latest.hash == expected_prev_hash
    """

    def __init__(
        self,
        client: firestore.Client,
        collection: str = "conversations",
    ) -> None:
        """Inicializa store de auditoria.

        Args:
            client: Cliente Firestore
            collection: Nome da collection pai (padrão: "conversations")
        """
        self._client = client
        self._collection = collection

    def _audit_collection(self, user_key: str) -> firestore.CollectionReference:
        """Retorna referência à subcollection de auditoria do usuário.

        Args:
            user_key: Chave do usuário (e.g., derivada de phone + hash)

        Returns:
            CollectionReference para /conversations/{user_key}/audit
        """
        return self._client.collection(self._collection).document(user_key).collection("audit")

    def get_latest_event(self, user_key: str) -> AuditEvent | None:
        """Recupera último evento da auditoria.

        Args:
            user_key: Chave do usuário

        Returns:
            Último evento ou None se não existe
        """
        query = (
            self._audit_collection(user_key)
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(1)
        )

        docs = list(query.stream())
        if not docs:
            return None

        doc_dict = docs[0].to_dict()
        if not doc_dict:
            return None

        try:
            return AuditEvent(**doc_dict)
        except Exception as e:
            logger.error(
                "Falha ao desserializar evento de auditoria",
                extra={"user_key": user_key, "error": str(e)},
            )
            return None

    def list_events(
        self,
        user_key: str,
        limit: int = 500,
    ) -> list[AuditEvent]:
        """Lista todos os eventos de um usuário (ordenado por timestamp asc).

        Args:
            user_key: Chave do usuário
            limit: Máximo de eventos a retornar

        Returns:
            Lista de eventos (mais antigo primeiro)
        """
        query = (
            self._audit_collection(user_key)
            .order_by("timestamp", direction=firestore.Query.ASCENDING)
            .limit(limit)
        )

        events: list[AuditEvent] = []
        for doc in query.stream():
            doc_dict = doc.to_dict()
            if doc_dict:
                try:
                    events.append(AuditEvent(**doc_dict))
                except Exception:
                    logger.warning(
                        "Evento malformado ignorado",
                        extra={"user_key": user_key, "doc_id": doc.id},
                    )
                    continue

        return events

    def append_event(
        self,
        event: AuditEvent,
        expected_prev_hash: str | None,
    ) -> bool:
        """Append condicional de evento com validação de cadeia.

        Usa Firestore transaction para garantir atomicidade.
        Retorna False se prev_hash não corresponde ao último evento.
        """
        audit_col = self._audit_collection(event.user_key)
        doc_ref = audit_col.document(event.event_id)
        transaction = self._client.transaction()

        @firestore.transactional
        def _txn(tx: firestore.Transaction) -> bool:
            return self._execute_append_txn(tx, audit_col, doc_ref, event, expected_prev_hash)

        return _txn(transaction)

    def _execute_append_txn(
        self,
        tx: firestore.Transaction,
        audit_col: firestore.CollectionReference,
        doc_ref: firestore.DocumentReference,
        event: AuditEvent,
        expected_prev_hash: str | None,
    ) -> bool:
        """Executa transação de append com validação de cadeia."""
        latest_hash = self._get_latest_hash_in_txn(tx, audit_col)

        if latest_hash != expected_prev_hash:
            logger.debug(
                "Conflito de cadeia",
                extra={
                    "user_key": event.user_key,
                    "expected": expected_prev_hash[:8] if expected_prev_hash else None,
                    "actual": latest_hash[:8] if latest_hash else None,
                },
            )
            return False

        tx.set(doc_ref, event.model_dump())
        logger.debug("Evento appendado", extra={"event_id": event.event_id, "action": event.action})
        return True

    def _get_latest_hash_in_txn(
        self, tx: firestore.Transaction, audit_col: firestore.CollectionReference
    ) -> str | None:
        """Recupera hash do último evento dentro de uma transação."""
        query = audit_col.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(1)
        docs = list(query.stream(transaction=tx))
        if not docs:
            return None
        doc_dict = docs[0].to_dict()
        return doc_dict.get("hash") if doc_dict else None
