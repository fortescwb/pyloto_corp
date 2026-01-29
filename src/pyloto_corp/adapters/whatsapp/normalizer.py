"""Normalização de payloads do WhatsApp.

Responsabilidade:
- Extrair mensagens do payload do webhook Meta
- Normalizar todos os tipos de conteúdo suportados
- Sanitizar dados e evitar exposição de PII
- Rastrear referências para payload bruto se necessário
"""

from __future__ import annotations

import json
from typing import Any

from pyloto_corp.adapters.whatsapp.models import NormalizedWhatsAppMessage
from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)

# Tipos de mensagem suportados pela API Meta/WhatsApp
_SUPPORTED_TYPES = frozenset({
    "text", "image", "video", "audio", "document", "sticker",
    "location", "address", "contacts", "interactive", "reaction",
    "button", "order", "system", "request_welcome", "ephemeral",
})


def _extract_text_message(
    msg: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Extrai texto de uma mensagem de texto.

    Retorna (text_body, media_url) - media_url é None para texto puro.
    """
    text_block = msg.get("text") or {}
    if isinstance(text_block, dict):
        return text_block.get("body"), None
    return None, None


def _extract_media_message(
    msg: dict[str, Any], media_type: str
) -> tuple[str | None, str | None, str | None, str | None]:
    """Extrai mídia de uma mensagem (image, video, audio, document, sticker).

    Retorna (media_id, media_url, media_filename, media_mime_type).
    """
    media_block = msg.get(media_type) or {}
    if not isinstance(media_block, dict):
        return None, None, None, None

    media_id = media_block.get("id")
    media_url = media_block.get("url")
    media_filename = media_block.get("filename")
    media_mime_type = media_block.get("mime_type")

    return media_id, media_url, media_filename, media_mime_type


def _extract_location_message(
    msg: dict[str, Any],
) -> tuple[float | None, float | None, str | None, str | None]:
    """Extrai localização de uma mensagem."""
    location_block = msg.get("location") or {}
    if not isinstance(location_block, dict):
        return None, None, None, None

    return (
        location_block.get("latitude"),
        location_block.get("longitude"),
        location_block.get("name"),
        location_block.get("address"),
    )


def _extract_address_message(
    msg: dict[str, Any],
) -> tuple[str | None, str | None, str | None, str | None, str | None]:
    """Extrai endereço de uma mensagem.
    
    Retorna (street, city, state, zip_code, country_code).
    """
    address_block = msg.get("address") or {}
    if not isinstance(address_block, dict):
        return None, None, None, None, None

    return (
        address_block.get("street"),
        address_block.get("city"),
        address_block.get("state"),
        address_block.get("zip_code"),
        address_block.get("country_code"),
    )


def _extract_contacts_message(msg: dict[str, Any]) -> str | None:
    """Extrai contatos de uma mensagem (serializado como JSON).

    Nunca retorna o objeto bruto - sempre JSON serializado para segurança.
    """
    contacts_block = msg.get("contacts") or []
    if not isinstance(contacts_block, list) or not contacts_block:
        return None

    try:
        return json.dumps(contacts_block, ensure_ascii=False)
    except (TypeError, ValueError):
        return None


def _extract_interactive_message(
    msg: dict[str, Any],
) -> tuple[str | None, str | None, str | None]:
    """Extrai dados de mensagem interativa.

    Retorna (interactive_type, button_id/list_id, None).
    """
    interactive_block = msg.get("interactive") or {}
    if not isinstance(interactive_block, dict):
        return None, None, None

    interactive_type = interactive_block.get("type")  # button, list, flow, etc.

    # Para button replies
    button_reply = interactive_block.get("button_reply") or {}
    if isinstance(button_reply, dict):
        button_id = button_reply.get("id")
        if button_id:
            return interactive_type, button_id, None

    # Para list replies
    list_reply = interactive_block.get("list_reply") or {}
    if isinstance(list_reply, dict):
        list_id = list_reply.get("id")
        if list_id:
            return interactive_type, None, list_id

    return interactive_type, None, None


def _extract_reaction_message(msg: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extrai reação (emoji) a mensagem.

    Retorna (reaction_message_id, reaction_emoji).
    """
    reaction_block = msg.get("reaction") or {}
    if not isinstance(reaction_block, dict):
        return None, None

    return (
        reaction_block.get("message_id"),
        reaction_block.get("emoji"),
    )


def _create_empty_fields() -> dict[str, Any]:
    """Inicializa dicionário com todos os campos de mensagem como None.

    Retorna dicionário com campos padrão para NormalizedWhatsAppMessage.
    """
    return {
        "text": None,
        "media_id": None,
        "media_url": None,
        "media_filename": None,
        "media_mime_type": None,
        "location_latitude": None,
        "location_longitude": None,
        "location_name": None,
        "location_address": None,
        "address_street": None,
        "address_city": None,
        "address_state": None,
        "address_zip_code": None,
        "address_country_code": None,
        "contacts_json": None,
        "interactive_type": None,
        "interactive_button_id": None,
        "interactive_list_id": None,
        "interactive_cta_url": None,
        "reaction_message_id": None,
        "reaction_emoji": None,
    }


def _extract_fields_by_type(
    msg: dict[str, Any], message_type: str, fields: dict[str, Any]
) -> None:
    """Popula campos específicos conforme tipo de mensagem.

    Modifica dicionário `fields` in-place com valores extraídos.

    Args:
        msg: Mensagem bruta do webhook Meta
        message_type: Tipo da mensagem (text, image, location, etc.)
        fields: Dicionário de campos a ser preenchido
    """
    if message_type == "text":
        fields["text"], _ = _extract_text_message(msg)

    elif message_type in ("image", "video", "audio", "document", "sticker"):
        (
            fields["media_id"],
            fields["media_url"],
            fields["media_filename"],
            fields["media_mime_type"],
        ) = _extract_media_message(msg, message_type)

    elif message_type == "location":
        (
            fields["location_latitude"],
            fields["location_longitude"],
            fields["location_name"],
            fields["location_address"],
        ) = _extract_location_message(msg)

    elif message_type == "address":
        (
            fields["address_street"],
            fields["address_city"],
            fields["address_state"],
            fields["address_zip_code"],
            fields["address_country_code"],
        ) = _extract_address_message(msg)

    elif message_type == "contacts":
        fields["contacts_json"] = _extract_contacts_message(msg)

    elif message_type == "interactive":
        (
            fields["interactive_type"],
            fields["interactive_button_id"],
            fields["interactive_list_id"],
        ) = _extract_interactive_message(msg)
        # Também tenta extrair CTA URL se houver
        interactive_block = msg.get("interactive") or {}
        if isinstance(interactive_block, dict):
            cta_block = interactive_block.get("cta_url_reply") or {}
            if isinstance(cta_block, dict):
                fields["interactive_cta_url"] = cta_block.get("url")

    elif message_type == "reaction":
        (
            fields["reaction_message_id"],
            fields["reaction_emoji"],
        ) = _extract_reaction_message(msg)

    else:
        # Tipo não mapeado - logar para observabilidade sem PII
        if message_type and message_type not in _SUPPORTED_TYPES:
            logger.info(
                "unsupported_message_type_received",
                extra={"message_type": message_type},
            )


def extract_messages(payload: dict[str, Any]) -> list[NormalizedWhatsAppMessage]:
    """Extrai todas as mensagens do payload do webhook Meta.

    Suporta todos os tipos de conteúdo conforme API Meta:
    - text
    - image, video, audio, document, sticker
    - location
    - contacts
    - interactive (button, list, flow)
    - reaction

    Args:
        payload: Payload bruto do webhook Meta

    Returns:
        Lista de mensagens normalizadas (sem PII no texto)
    """
    messages: list[NormalizedWhatsAppMessage] = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})

            for msg in value.get("messages", []) or []:
                message_id = msg.get("id")
                if not message_id:
                    continue

                from_number = msg.get("from")
                timestamp = msg.get("timestamp")
                message_type = msg.get("type")

                # Inicializar campos opcionais.
                fields = _create_empty_fields()
                # Extrair campos específicos conforme tipo de mensagem.
                _extract_fields_by_type(msg, message_type, fields)

                # Constrói mensagem normalizada
                normalized = NormalizedWhatsAppMessage(
                    message_id=message_id,
                    from_number=from_number,
                    timestamp=timestamp,
                    message_type=message_type or "unknown",
                    **fields,
                )

                messages.append(normalized)

    return messages
