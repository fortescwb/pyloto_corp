from __future__ import annotations

from typing import Any

from pyloto_corp.adapters.whatsapp.models import NormalizedWhatsAppMessage

from .extractor import extract_payload_messages
from .sanitizer import sanitize_message_payload
from .validator import is_valid_message_data


def _build_normalized_message(message_data: dict[str, Any]) -> NormalizedWhatsAppMessage:
    fields = message_data.get("fields") or {}
    return NormalizedWhatsAppMessage(
        message_id=message_data["message_id"],
        from_number=message_data.get("from_number"),
        timestamp=message_data.get("timestamp"),
        message_type=message_data.get("message_type", "unknown"),
        **fields,
    )


def normalize_messages(payload: dict[str, Any]) -> list[NormalizedWhatsAppMessage]:
    """Normaliza mensagens do payload Meta para modelos internos."""
    normalized_messages: list[NormalizedWhatsAppMessage] = []

    for message_data in extract_payload_messages(payload):
        sanitized = sanitize_message_payload(message_data)
        if not is_valid_message_data(sanitized):
            continue
        normalized_messages.append(_build_normalized_message(sanitized))

    return normalized_messages


def extract_messages(payload: dict[str, Any]) -> list[NormalizedWhatsAppMessage]:
    """Compat: mantém assinatura pública usada pelos pipelines."""
    return normalize_messages(payload)


def normalize_message(payload: dict[str, Any]) -> list[NormalizedWhatsAppMessage]:
    """Alias compatível para import legado."""
    return normalize_messages(payload)
