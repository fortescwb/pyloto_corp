"""Factory para OutboundDedupeStore — Criação Backend-Agnóstica.

Responsabilidades:
- Criar instâncias de OutboundDedupeStore baseado em config
- Validar clientes obrigatórios
- Registrar escolha de backend

Conforme regras_e_padroes.md (factory pattern, injeção de dependência).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pyloto_corp.domain.outbound_dedup import OutboundDedupeStore
from pyloto_corp.infra.outbound_dedup_firestore import FirestoreOutboundDedupeStore
from pyloto_corp.infra.outbound_dedup_memory import InMemoryOutboundDedupeStore
from pyloto_corp.infra.outbound_dedup_redis import RedisOutboundDedupeStore
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    pass

logger: logging.Logger = get_logger(__name__)


def create_outbound_dedupe_store(
    backend: str,
    redis_client: Any | None = None,
    firestore_client: Any | None = None,
) -> OutboundDedupeStore:
    """Factory para OutboundDedupeStore.

    Args:
        backend: "redis", "firestore" ou "memory"
        redis_client: Cliente Redis (obrigatório se backend="redis")
        firestore_client: Cliente Firestore (obrigatório se backend="firestore")

    Returns:
        OutboundDedupeStore configurado

    Raises:
        ValueError: Se backend inválido ou cliente não fornecido
    """
    if backend == "memory":
        logger.warning("Using in-memory outbound dedupe store (dev only)")
        return InMemoryOutboundDedupeStore()

    if backend == "redis":
        if not redis_client:
            msg = "redis_client required for redis backend"
            raise ValueError(msg)
        logger.info("Using Redis outbound dedupe store")
        return RedisOutboundDedupeStore(redis_client)

    if backend == "firestore":
        if not firestore_client:
            msg = "firestore_client required for firestore backend"
            raise ValueError(msg)
        logger.info("Using Firestore outbound dedupe store")
        return FirestoreOutboundDedupeStore(firestore_client)

    msg = f"Unknown outbound dedupe backend: {backend}"
    raise ValueError(msg)
