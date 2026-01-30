"""OutboundDedupeStore em Redis — Para Produção.

Responsabilidades:
- Implementar OutboundDedupeStore usando Redis
- Usar SETNX para atomicidade
- Gerenciar TTL nativo do Redis
- Fail-closed em caso de indisponibilidade

Conforme regras_e_padroes.md (SRP, implementação isolada, zero-trust).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pyloto_corp.domain.outbound_dedup import DedupeResult, OutboundDedupeError, OutboundDedupeStore
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    pass

logger: logging.Logger = get_logger(__name__)


class RedisOutboundDedupeStore(OutboundDedupeStore):
    """Store Redis para produção.

    Usa SETNX para atomicidade e TTL nativo do Redis.
    Fail-closed: lança exceção se Redis indisponível.

    Estrutura Redis:
        KEY: outbound:{idempotency_key}
        VALUE: {"message_id": "...", "timestamp": "2026-01-25T..."}
        EXPIRE: TTL segundos (automático)
    """

    def __init__(self, redis_client: Any, key_prefix: str = "outbound:") -> None:
        self._redis = redis_client
        self._prefix = key_prefix

    def check_and_mark(
        self,
        idempotency_key: str,
        message_id: str,
        ttl_seconds: int | None = None,
    ) -> DedupeResult:
        """Verifica e marca atomicamente com SETNX."""
        ttl = ttl_seconds or self.DEFAULT_TTL_SECONDS
        key = f"{self._prefix}{idempotency_key}"

        try:
            now = datetime.now(tz=UTC)
            value = json.dumps(
                {
                    "message_id": message_id,
                    "timestamp": now.isoformat(),
                    "status": "pending",
                    "error": None,
                }
            )

            # SETNX: set only if not exists, com EXPIRE
            was_set = self._redis.set(key, value, nx=True, ex=ttl)

            if was_set:
                logger.debug(
                    "Outbound dedup miss (Redis)",
                    extra={"key_prefix": idempotency_key[:8] + "..."},
                )
                return DedupeResult(is_duplicate=False)

            # Já existe, buscar dados originais
            existing = self._redis.get(key)
            if existing:
                if isinstance(existing, bytes):
                    existing = existing.decode("utf-8")
                data = json.loads(existing)
                logger.debug(
                    "Outbound dedup hit (Redis)",
                    extra={"key_prefix": idempotency_key[:8] + "..."},
                )
                return DedupeResult(
                    is_duplicate=True,
                    original_message_id=data.get("message_id"),
                    original_timestamp=datetime.fromisoformat(data["timestamp"]),
                    status=data.get("status"),
                    error=data.get("error"),
                )

            return DedupeResult(is_duplicate=True)

        except Exception as e:
            logger.error(
                "Redis outbound dedup failed (fail-closed)",
                extra={"error": str(e)},
            )
            raise OutboundDedupeError(f"Redis unavailable: {e}") from e

    def is_sent(self, idempotency_key: str) -> bool:
        """Verifica se já enviado (fail-closed)."""
        key = f"{self._prefix}{idempotency_key}"

        try:
            if not self._redis.exists(key):
                return False
            existing = self._redis.get(key)
            if not existing:
                return False
            if isinstance(existing, bytes):
                existing = existing.decode("utf-8")
            data = json.loads(existing)
            return data.get("status") == "sent"
        except Exception as e:
            logger.error(
                "Redis outbound dedup check failed (fail-closed)",
                extra={"error": str(e)},
            )
            raise OutboundDedupeError(f"Redis unavailable: {e}") from e

    def mark_sent(
        self,
        idempotency_key: str,
        message_id: str,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Marca como enviado (fail-closed)."""
        ttl = ttl_seconds or self.DEFAULT_TTL_SECONDS
        key = f"{self._prefix}{idempotency_key}"

        try:
            now = datetime.now(tz=UTC)
            value = json.dumps(
                {
                    "message_id": message_id,
                    "timestamp": now.isoformat(),
                    "status": "sent",
                    "error": None,
                }
            )

            # Atualiza sempre, preservando TTL
            self._redis.set(key, value, ex=ttl)
            return True

        except Exception as e:
            logger.error(
                "Redis outbound dedup mark failed (fail-closed)",
                extra={"error": str(e)},
            )
            raise OutboundDedupeError(f"Redis unavailable: {e}") from e

    def mark_failed(
        self,
        idempotency_key: str,
        error: str | None = None,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Marca envio como falho (fail-closed)."""
        ttl = ttl_seconds or self.DEFAULT_TTL_SECONDS
        key = f"{self._prefix}{idempotency_key}"

        try:
            now = datetime.now(tz=UTC)
            value = json.dumps(
                {
                    "message_id": idempotency_key,
                    "timestamp": now.isoformat(),
                    "status": "failed",
                    "error": error,
                }
            )
            self._redis.set(key, value, ex=ttl)
            return True
        except Exception as e:
            logger.error(
                "Redis outbound dedup mark failed (fail-closed)",
                extra={"error": str(e)},
            )
            raise OutboundDedupeError(f"Redis unavailable: {e}") from e

    def get_status(self, idempotency_key: str) -> str | None:
        """Retorna status armazenado ou None."""
        key = f"{self._prefix}{idempotency_key}"
        try:
            existing = self._redis.get(key)
            if not existing:
                return None
            if isinstance(existing, bytes):
                existing = existing.decode("utf-8")
            data = json.loads(existing)
            return data.get("status")
        except Exception as e:
            logger.error(
                "Redis outbound dedup status failed (fail-closed)",
                extra={"error": str(e)},
            )
            raise OutboundDedupeError(f"Redis unavailable: {e}") from e
