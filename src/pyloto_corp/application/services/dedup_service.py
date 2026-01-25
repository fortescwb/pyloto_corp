"""Serviço de Deduplicação — Lógica de Chave de Idempotência.

Responsabilidades:
- Gerar chaves de idempotência determinísticas
- Hashear conteúdo de mensagens
- Gerenciar janelas de tempo

Conforme regras_e_padroes.md (SRP, lógica de negócio isolada).
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from pyloto_corp.observability.logging import get_logger

logger: logging.Logger = get_logger(__name__)


def generate_idempotency_key(
    recipient_id: str,
    content_hash: str,
    timestamp_window_minutes: int = 5,
) -> str:
    """Gera chave de idempotência para mensagem outbound.

    Determinística: mesmo input sempre produz mesma chave.

    Args:
        recipient_id: ID do destinatário (phone number ID)
        content_hash: Hash do conteúdo da mensagem (SHA256)
        timestamp_window_minutes: Janela de tempo para considerar duplicata

    Returns:
        Chave de idempotência (SHA256 hex)
    """
    now = datetime.now(tz=UTC)
    window_start = now.replace(
        minute=(now.minute // timestamp_window_minutes) * timestamp_window_minutes,
        second=0,
        microsecond=0,
    )
    window_str = window_start.strftime("%Y%m%d%H%M")

    combined = f"{recipient_id}:{content_hash}:{window_str}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def hash_message_content(content: dict[str, Any]) -> str:
    """Gera hash do conteúdo da mensagem para deduplicação.

    Determinística: mesmo payload sempre produz mesmo hash.
    Ignora ordem de chaves (ordena antes de serializar).

    Args:
        content: Payload da mensagem (sem recipient)

    Returns:
        Hash SHA256 hex
    """
    serialized = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
