"""Compat depreciação — Outbound dedupe consolidado.

Este arquivo existia como God Module (495 linhas). Para eliminar duplicação
crítica, ele foi reduzido a um shim de compatibilidade que reexporta o
contrato e as implementações modulares:
- domínio: pyloto_corp.domain.outbound_dedup
- infra (impls): outbound_dedup_memory, outbound_dedup_redis, outbound_dedup_firestore
- factory: outbound_dedup_factory.create_outbound_dedupe_store

Qualquer novo código deve importar diretamente dos módulos modulares. Este
shim permanece apenas para evitar imports legados quebrarem durante a transição.
"""

from __future__ import annotations

from pyloto_corp.domain.outbound_dedup import (  # noqa: F401
    DedupeResult,
    OutboundDedupeError,
    OutboundDedupeStore,
)
from pyloto_corp.infra.outbound_dedup_factory import (  # noqa: F401
    create_outbound_dedupe_store,
)
from pyloto_corp.infra.outbound_dedup_firestore import FirestoreOutboundDedupeStore  # noqa: F401
from pyloto_corp.infra.outbound_dedup_memory import InMemoryOutboundDedupeStore  # noqa: F401
from pyloto_corp.infra.outbound_dedup_redis import RedisOutboundDedupeStore  # noqa: F401

# Constante mantida para compatibilidade com o módulo antigo
DEFAULT_TTL_SECONDS = OutboundDedupeStore.DEFAULT_TTL_SECONDS


def hash_message_content(content: dict) -> str:
    """Compatibilidade com hash do módulo legado (JSON ordenado)."""
    import json

    serialized = json.dumps(content, sort_keys=True, ensure_ascii=False)
    import hashlib

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


__all__ = [
    "DedupeResult",
    "OutboundDedupeError",
    "OutboundDedupeStore",
    "InMemoryOutboundDedupeStore",
    "RedisOutboundDedupeStore",
    "FirestoreOutboundDedupeStore",
    "create_outbound_dedupe_store",
    "hash_message_content",
    "DEFAULT_TTL_SECONDS",
]
