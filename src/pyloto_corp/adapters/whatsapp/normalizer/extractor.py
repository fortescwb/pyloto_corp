from __future__ import annotations

import json
from typing import Any

from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)

SUPPORTED_MESSAGE_TYPES = frozenset(
    {
        "text", "image", "video", "audio",
        "document", "sticker", "location", "address",
        "contacts", "interactive", "reaction", "button",
        "order", "system", "request_welcome", "ephemeral",
    }
)

_FIELD_NAMES = (
    "text", "media_id", "media_url", "media_filename", "media_mime_type",
    "location_latitude", "location_longitude", "location_name", "location_address",
    "address_street", "address_city", "address_state", "address_zip_code", "address_country_code",
    "contacts_json", "interactive_type", "interactive_button_id", "interactive_list_id",
    "interactive_cta_url", "reaction_message_id", "reaction_emoji",
)


def _extract_text_message(msg: dict[str, Any]) -> tuple[str | None, str | None]:
    text_block = msg.get("text")
    if isinstance(text_block, dict):
        return text_block.get("body"), None
    return None, None


def _extract_media_message(
    msg: dict[str, Any], media_type: str
) -> tuple[str | None, str | None, str | None, str | None]:
    media_block = msg.get(media_type)
    if not isinstance(media_block, dict):
        return None, None, None, None
    return (
        media_block.get("id"),
        media_block.get("url"),
        media_block.get("filename"),
        media_block.get("mime_type"),
    )


def _extract_location_message(
    msg: dict[str, Any],
) -> tuple[float | None, float | None, str | None, str | None]:
    location_block = msg.get("location")
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
    address_block = msg.get("address")
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
    interactive_block = msg.get("interactive")
    if not isinstance(interactive_block, dict):
        return None, None, None
    interactive_type = interactive_block.get("type")
    button_reply = interactive_block.get("button_reply") or {}
    if isinstance(button_reply, dict):
        button_id = button_reply.get("id")
        if button_id:
            return interactive_type, button_id, None
    list_reply = interactive_block.get("list_reply") or {}
    if isinstance(list_reply, dict):
        list_id = list_reply.get("id")
        if list_id:
            return interactive_type, None, list_id
    return interactive_type, None, None


def _extract_reaction_message(msg: dict[str, Any]) -> tuple[str | None, str | None]:
    reaction_block = msg.get("reaction")
    if not isinstance(reaction_block, dict):
        return None, None
    return reaction_block.get("message_id"), reaction_block.get("emoji")


def _create_empty_fields() -> dict[str, Any]:
    return dict.fromkeys(_FIELD_NAMES, None)

def _extract_fields_by_type(
    msg: dict[str, Any],
    message_type: str | None,
    fields: dict[str, Any],
) -> None:
    if message_type == "text":
        fields["text"], _ = _extract_text_message(msg)
        return
    if message_type in ("image", "video", "audio", "document", "sticker"):
        (
            fields["media_id"],
            fields["media_url"],
            fields["media_filename"],
            fields["media_mime_type"],
        ) = _extract_media_message(msg, message_type)
        return
    if message_type == "location":
        (
            fields["location_latitude"],
            fields["location_longitude"],
            fields["location_name"],
            fields["location_address"],
        ) = _extract_location_message(msg)
        return
    if message_type == "address":
        (
            fields["address_street"],
            fields["address_city"],
            fields["address_state"],
            fields["address_zip_code"],
            fields["address_country_code"],
        ) = _extract_address_message(msg)
        return
    if message_type == "contacts":
        fields["contacts_json"] = _extract_contacts_message(msg)
        return
    if message_type == "interactive":
        (
            fields["interactive_type"],
            fields["interactive_button_id"],
            fields["interactive_list_id"],
        ) = _extract_interactive_message(msg)
        interactive_block = msg.get("interactive") or {}
        if isinstance(interactive_block, dict):
            cta_block = interactive_block.get("cta_url_reply") or {}
            if isinstance(cta_block, dict):
                fields["interactive_cta_url"] = cta_block.get("url")
        return
    if message_type == "reaction":
        (
            fields["reaction_message_id"],
            fields["reaction_emoji"],
        ) = _extract_reaction_message(msg)
        return
    if message_type and message_type not in SUPPORTED_MESSAGE_TYPES:
        logger.info("unsupported_message_type_received", extra={"message_type": message_type})


def extract_payload_messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extrai mensagens do payload bruto para estrutura intermediária."""
    messages: list[dict[str, Any]] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []) or []:
                message_id = msg.get("id")
                if not message_id:
                    continue
                message_type = msg.get("type")
                fields = _create_empty_fields()
                _extract_fields_by_type(msg, message_type, fields)
                messages.append(
                    {
                        "message_id": message_id,
                        "from_number": msg.get("from"),
                        "timestamp": msg.get("timestamp"),
                        "message_type": message_type or "unknown",
                        "fields": fields,
                    }
                )
    return messages
