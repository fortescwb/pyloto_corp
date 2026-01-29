"""OutboundDedupeStore em Memória — Para Desenvolvimento e Testes.

Responsabilidades:
- Implementar OutboundDedupeStore usando dict em memória
- Gerenciar TTL e limpeza de entradas expiradas
- ⚠️ Não usar em produção

Conforme regras_e_padroes.md (SRP, implementação isolada).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pyloto_corp.domain.outbound_dedup import DedupeResult, OutboundDedupeStore
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    pass

logger: logging.Logger = get_logger(__name__)


class InMemoryOutboundDedupeStore(OutboundDedupeStore):
    """Store em memória para desenvolvimento e testes.

    ⚠️ Não usar em produção! Dados são perdidos ao reiniciar.

    Estrutura interna:
        {idempotency_key: (message_id, timestamp, expire_at)}
    """

    def __init__(self) -> None:
        # {idempotency_key: (message_id, timestamp, expire_at_seconds, status, error)}
        self._store: dict[str, tuple[str, datetime, float, str, str | None]] = {}

    def check_and_mark(
        self,
        idempotency_key: str,
        message_id: str,
        ttl_seconds: int | None = None,
    ) -> DedupeResult:
        """Verifica e marca em memória (com expiração)."""
        ttl = ttl_seconds or self.DEFAULT_TTL_SECONDS
        self._cleanup_expired()

        if idempotency_key in self._store:
            existing = self._store[idempotency_key]
            logger.debug(
                "Outbound dedup hit (in-memory)",
                extra={"key_prefix": idempotency_key[:8] + "..."},
            )
            return DedupeResult(
                is_duplicate=True,
                original_message_id=existing[0],
                original_timestamp=existing[1],
                status=existing[3],
                error=existing[4],
            )

        now = datetime.now(tz=UTC)
        expire_at = now.timestamp() + ttl
        self._store[idempotency_key] = (message_id, now, expire_at, "pending", None)

        logger.debug(
            "Outbound dedup miss (in-memory)",
            extra={"key_prefix": idempotency_key[:8] + "..."},
        )
        return DedupeResult(is_duplicate=False)

    def is_sent(self, idempotency_key: str) -> bool:
        """Verifica se já enviado."""
        self._cleanup_expired()
        record = self._store.get(idempotency_key)
        return bool(record and record[3] == "sent")

    def mark_sent(
        self,
        idempotency_key: str,
        message_id: str,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Marca como enviado."""
        ttl = ttl_seconds or self.DEFAULT_TTL_SECONDS
        now = datetime.now(tz=UTC)
        expire_at = now.timestamp() + ttl
        existing = self._store.get(idempotency_key)
        if existing and existing[3] == "sent":
            return False

        self._store[idempotency_key] = (message_id, now, expire_at, "sent", None)
        return True

    def mark_failed(
        self,
        idempotency_key: str,
        error: str | None = None,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Marca envio como falho (não limpa idempotência)."""
        ttl = ttl_seconds or self.DEFAULT_TTL_SECONDS
        now = datetime.now(tz=UTC)
        expire_at = now.timestamp() + ttl

        existing = self._store.get(idempotency_key)
        if existing and existing[3] == "failed":
            return False

        message_id = existing[0] if existing else idempotency_key
        self._store[idempotency_key] = (message_id, now, expire_at, "failed", error)
        return True

    def get_status(self, idempotency_key: str) -> str | None:
        """Retorna status atual ou None se expirado."""
        self._cleanup_expired()
        record = self._store.get(idempotency_key)
        if not record:
            return None
        return record[3]

    def _cleanup_expired(self) -> None:
        """Remove entradas expiradas."""
        now = datetime.now(tz=UTC).timestamp()
        expired = [k for k, v in self._store.items() if v[2] < now]
        for k in expired:
            del self._store[k]
