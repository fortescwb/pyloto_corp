"""Builder para mensagens de texto."""

from __future__ import annotations

from typing import Any

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest


class TextPayloadBuilder:
    """Builder para mensagens de texto simples."""

    def build(self, request: OutboundMessageRequest) -> dict[str, Any]:
        """Constrói payload para mensagem de texto.

        Args:
            request: Requisição de envio

        Returns:
            Payload de texto conforme API Meta
        """
        return {
            "text": {
                "preview_url": False,
                "body": request.text,
            }
        }
