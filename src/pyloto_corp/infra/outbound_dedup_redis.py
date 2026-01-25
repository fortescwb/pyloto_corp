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
            value = json.dumps({
                "message_id": message_id,
                "timestamp": now.isoformat(),
            })

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
            return bool(self._redis.exists(key))
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
            value = json.dumps({
                "message_id": message_id,
                "timestamp": now.isoformat(),
            })

            was_set = self._redis.set(key, value, nx=True, ex=ttl)
            return bool(was_set)

        except Exception as e:
            logger.error(
                "Redis outbound dedup mark failed (fail-closed)",
                extra={"error": str(e)},
            )
            raise OutboundDedupeError(f"Redis unavailable: {e}") from e
