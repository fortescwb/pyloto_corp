"""Builder para mensagens de template."""

from __future__ import annotations

from typing import Any

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest


class TemplatePayloadBuilder:
    """Builder para mensagens de template."""

    def build(self, request: OutboundMessageRequest) -> dict[str, Any]:
        """Constrói payload para mensagem de template.

        Args:
            request: Requisição com dados de template

        Returns:
            Payload template conforme API Meta
        """
        template_obj: dict[str, Any] = {
            "name": request.template_name,
            "language": {"code": "pt_BR"},
        }

        if request.template_params:
            template_obj["components"] = [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": str(p)} for p in request.template_params.values()
                    ],
                }
            ]

        return {"template": template_obj}
