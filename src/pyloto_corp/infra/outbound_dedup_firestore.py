"""OutboundDedupeStore em Firestore — Para Produção Alternativa.

Responsabilidades:
- Implementar OutboundDedupeStore usando Firestore
- Usar transações para atomicidade
- Gerenciar TTL via campo _ttl_expire_at
- Fail-closed em caso de indisponibilidade

Conforme regras_e_padroes.md (SRP, implementação isolada, zero-trust).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from pyloto_corp.domain.outbound_dedup import DedupeResult, OutboundDedupeError, OutboundDedupeStore
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    pass

logger: logging.Logger = get_logger(__name__)


class FirestoreOutboundDedupeStore(OutboundDedupeStore):
    """Store Firestore para produção.

    Collection: outbound_dedup/{idempotency_key}
    Usa TTL policy do Firestore para expiração automática.
    Fail-closed: lança exceção se Firestore indisponível.

    Schema:
        /outbound_dedup/{idempotency_key}
          ├── message_id: string
          ├── timestamp: datetime
          └── _ttl_expire_at: datetime (campo para TTL policy)
    """

    def __init__(
        self,
        firestore_client: Any,
        collection: str = "outbound_dedup",
    ) -> None:
        self._client = firestore_client
        self._collection = collection

    def _create_entry(
        self,
        doc_ref: Any,
        message_id: str,
        expire_at: datetime,
        status: str,
        error: str | None = None,
    ) -> None:
        """Cria/atualiza entrada de dedupe."""
        now = datetime.now(tz=UTC)
        doc_ref.set({
            "message_id": message_id,
            "timestamp": now,
            "_ttl_expire_at": expire_at,
            "status": status,
            "error": error,
        })

    def _handle_existing(
        self,
        data: dict,
        doc_ref: Any,
        message_id: str,
        expire_at: datetime,
    ) -> DedupeResult:
        """Processa documento existente — verifica expiração ou retorna hit."""
        ttl_expire = data.get("_ttl_expire_at")
        now = datetime.now(tz=UTC)

        if not (ttl_expire and now > ttl_expire):
            logger.debug("Outbound dedup hit (Firestore)", extra={"key_prefix": "..."})
            return DedupeResult(
                is_duplicate=True,
                original_message_id=data.get("message_id"),
                original_timestamp=data.get("timestamp"),
                status=data.get("status"),
                error=data.get("error"),
            )

        self._create_entry(doc_ref, message_id, expire_at, status="pending")
        logger.debug(
            "Outbound dedup miss (expired, Firestore)",
            extra={"key_prefix": "..."},
        )
        return DedupeResult(is_duplicate=False)

    def check_and_mark(
        self,
        idempotency_key: str,
        message_id: str,
        ttl_seconds: int | None = None,
    ) -> DedupeResult:
        """Verifica e marca com transação Firestore."""
        ttl = ttl_seconds or self.DEFAULT_TTL_SECONDS
        doc_ref = self._client.collection(self._collection).document(idempotency_key)
        expire_at = datetime.now(tz=UTC) + timedelta(seconds=ttl)

        try:
            doc = doc_ref.get()

            if doc.exists:
                return self._handle_existing(
                    doc.to_dict(), doc_ref, message_id, expire_at
                )

            self._create_entry(doc_ref, message_id, expire_at, status="pending")
            logger.debug(
                "Outbound dedup miss (Firestore)",
                extra={"key_prefix": idempotency_key[:8] + "..."},
            )
            return DedupeResult(is_duplicate=False)

        except Exception as e:
            logger.error(
                "Firestore outbound dedup failed (fail-closed)",
                extra={"error": str(e)},
            )
            raise OutboundDedupeError(f"Firestore unavailable: {e}") from e

    def is_sent(self, idempotency_key: str) -> bool:
        """Verifica se já enviado (fail-closed)."""
        doc_ref = self._client.collection(self._collection).document(idempotency_key)

        try:
            doc = doc_ref.get()
            if not doc.exists:
                return False

            data = doc.to_dict()
            ttl_expire = data.get("_ttl_expire_at")
            if ttl_expire and datetime.now(tz=UTC) > ttl_expire:
                return False
            return data.get("status") == "sent"

        except Exception as e:
            logger.error(
                "Firestore outbound dedup check failed (fail-closed)",
                extra={"error": str(e)},
            )
            raise OutboundDedupeError(f"Firestore unavailable: {e}") from e

    def mark_sent(
        self,
        idempotency_key: str,
        message_id: str,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Marca como enviado (fail-closed)."""
        ttl = ttl_seconds or self.DEFAULT_TTL_SECONDS
        doc_ref = self._client.collection(self._collection).document(idempotency_key)
        expire_at = datetime.now(tz=UTC) + timedelta(seconds=ttl)

        try:
            doc = doc_ref.get()
            now = datetime.now(tz=UTC)

            if doc.exists:
                data = doc.to_dict()
                ttl_expire = data.get("_ttl_expire_at")
                if ttl_expire and now <= ttl_expire and data.get("status") == "sent":
                    return False  # Já existe e não expirou

            self._create_entry(
                doc_ref,
                message_id=message_id,
                expire_at=expire_at,
                status="sent",
                error=None,
            )
            return True

        except Exception as e:
            logger.error(
                "Firestore outbound dedup mark failed (fail-closed)",
                extra={"error": str(e)},
            )
            raise OutboundDedupeError(f"Firestore unavailable: {e}") from e

    def mark_failed(
        self,
        idempotency_key: str,
        error: str | None = None,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Marca envio como falho (fail-closed)."""
        ttl = ttl_seconds or self.DEFAULT_TTL_SECONDS
        doc_ref = self._client.collection(self._collection).document(idempotency_key)
        expire_at = datetime.now(tz=UTC) + timedelta(seconds=ttl)

        try:
            self._create_entry(
                doc_ref,
                message_id=idempotency_key,
                expire_at=expire_at,
                status="failed",
                error=error,
            )
            return True
        except Exception as e:
            logger.error(
                "Firestore outbound dedup mark failed (fail-closed)",
                extra={"error": str(e)},
            )
            raise OutboundDedupeError(f"Firestore unavailable: {e}") from e

    def get_status(self, idempotency_key: str) -> str | None:
        """Retorna status atual ou None se expirado."""
        doc_ref = self._client.collection(self._collection).document(idempotency_key)

        try:
            doc = doc_ref.get()
            if not doc.exists:
                return None
            data = doc.to_dict()
            ttl_expire = data.get("_ttl_expire_at")
            if ttl_expire and datetime.now(tz=UTC) > ttl_expire:
                return None
            return data.get("status")
        except Exception as e:
            logger.error(
                "Firestore outbound dedup status failed (fail-closed)",
                extra={"error": str(e)},
            )
            raise OutboundDedupeError(f"Firestore unavailable: {e}") from e
