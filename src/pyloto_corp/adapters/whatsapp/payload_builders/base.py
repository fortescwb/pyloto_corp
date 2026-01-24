"""Interfaces e utilidades base para builders de payload."""

from __future__ import annotations

from typing import Any, Protocol

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest


class PayloadBuilder(Protocol):
    """Protocolo para builders de payload por tipo de mensagem."""

    def build(
        self,
        request: OutboundMessageRequest,
    ) -> dict[str, Any]:
        """Constrói o payload específico para o tipo de mensagem.

        Args:
            request: Requisição de envio

        Returns:
            Payload parcial (será mesclado com base)
        """
        ...


def build_base_payload(request: OutboundMessageRequest) -> dict[str, Any]:
    """Constrói payload base comum a todas as mensagens.

    Args:
        request: Requisição de envio

    Returns:
        Payload com campos obrigatórios
    """
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": request.to,
        "type": request.message_type,
    }
