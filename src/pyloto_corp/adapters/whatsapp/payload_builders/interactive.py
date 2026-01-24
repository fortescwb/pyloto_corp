"""Builders para mensagens interativas (botões, lista, flow, CTA)."""

from __future__ import annotations

from typing import Any

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest
from pyloto_corp.domain.enums import InteractiveType


def _build_button_action(request: OutboundMessageRequest) -> dict[str, Any]:
    """Constrói action para tipo BUTTON."""
    return {
        "buttons": [
            {
                "type": "reply",
                "reply": {"id": btn["id"], "title": btn["title"]},
            }
            for btn in (request.buttons or [])
        ]
    }


def _build_list_action(request: OutboundMessageRequest) -> dict[str, Any]:
    """Constrói action para tipo LIST."""
    return {
        "button": "Ver opções",
        "sections": request.buttons or [],
    }


def _build_flow_action(request: OutboundMessageRequest) -> dict[str, Any]:
    """Constrói action para tipo FLOW."""
    return {
        "name": "flow",
        "parameters": {
            "flow_message_version": request.flow_message_version,
            "flow_token": request.flow_token,
            "flow_id": request.flow_id,
            "flow_cta": request.flow_cta,
            "flow_action": request.flow_action,
        },
    }


def _build_cta_url_action(request: OutboundMessageRequest) -> dict[str, Any]:
    """Constrói action para tipo CTA_URL."""
    return {
        "name": "cta_url",
        "parameters": {
            "display_text": request.cta_display_text,
            "url": request.cta_url,
        },
    }


def _build_location_request_action() -> dict[str, Any]:
    """Constrói action para tipo LOCATION_REQUEST_MESSAGE."""
    return {"name": "send_location"}


# Mapeamento de tipo interativo para builder de action
_ACTION_BUILDERS: dict[InteractiveType, Any] = {
    InteractiveType.BUTTON: _build_button_action,
    InteractiveType.LIST: _build_list_action,
    InteractiveType.FLOW: _build_flow_action,
    InteractiveType.CTA_URL: _build_cta_url_action,
}


class InteractivePayloadBuilder:
    """Builder para mensagens interativas."""

    def build(self, request: OutboundMessageRequest) -> dict[str, Any]:
        """Constrói payload para mensagem interativa.

        Args:
            request: Requisição com dados interativos

        Returns:
            Payload interactive conforme API Meta
        """
        int_type = InteractiveType(request.interactive_type)

        interactive_obj: dict[str, Any] = {
            "type": int_type.value,
            "body": {"text": request.text},
        }

        # Obtém builder de action específico
        action_builder = _ACTION_BUILDERS.get(int_type)
        if action_builder:
            interactive_obj["action"] = action_builder(request)
        elif int_type == InteractiveType.LOCATION_REQUEST_MESSAGE:
            interactive_obj["action"] = _build_location_request_action()

        # Adiciona footer se presente
        if request.footer:
            interactive_obj["footer"] = {"text": request.footer}

        return {"interactive": interactive_obj}
