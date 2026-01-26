"""Construtor de payloads WhatsApp com validação e sanitização.

Responsabilidades:
- Construir payloads WhatsApp oficiais para cada tipo de mensagem
- Validar limites e constraints do canal
- Sanitizar dados sensíveis antes de logging
"""

from __future__ import annotations

import re
from typing import Any

from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)


def build_text_payload(to: str, text: str) -> dict[str, Any]:
    """Constrói payload de texto simples.

    Args:
        to: Número WhatsApp (com country code, ex: 5511999999999)
        text: Conteúdo de texto (máx 4096 chars)

    Returns:
        Dict conforme WhatsApp API spec
    """
    # Validar e truncar
    text = text.strip() if text else ""
    if len(text) > 4096:
        text = text[:4093] + "..."

    if not text:
        raise ValueError("Text content cannot be empty")

    return {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }


def build_interactive_buttons_payload(
    to: str,
    body: str,
    buttons: list[dict[str, str]],
    header: str | None = None,
    footer: str | None = None,
) -> dict[str, Any]:
    """Constrói payload com botões interativos.

    Args:
        to: Número WhatsApp
        body: Texto do corpo (máx 1024 chars)
        buttons: Lista de botões (máx 3, cada com id/title)
        header: Texto do cabeçalho (opcional, máx 60 chars)
        footer: Texto do rodapé (opcional, máx 60 chars)

    Returns:
        Dict conforme WhatsApp API spec
    """
    # Validar quantidade de botões
    if not buttons or len(buttons) > 3:
        raise ValueError(f"Buttons count must be 1-3, got {len(buttons)}")

    # Truncar e validar body
    body = body.strip() if body else ""
    if len(body) > 1024:
        body = body[:1021] + "..."

    if not body:
        raise ValueError("Body cannot be empty")

    # Preparar botões
    action_buttons = []
    for i, btn in enumerate(buttons[:3]):
        btn_id = btn.get("id", f"btn_{i}")
        btn_title = btn.get("title", "Opção")[:20]  # Máx 20 chars por botão
        action_buttons.append({
            "type": "reply",
            "reply": {
                "id": btn_id,
                "title": btn_title,
            }
        })

    # Montar payload
    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {"buttons": action_buttons},
        },
    }

    # Header e footer (opcionais)
    if header:
        header = header.strip()[:60]
        payload["interactive"]["header"] = {"type": "text", "text": header}

    if footer:
        footer = footer.strip()[:60]
        payload["interactive"]["footer"] = {"text": footer}

    return payload


def build_interactive_list_payload(
    to: str,
    body: str,
    sections: list[dict[str, Any]],
    header: str | None = None,
    button_text: str = "Selecione",
) -> dict[str, Any]:
    """Constrói payload com lista interativa.

    Args:
        to: Número WhatsApp
        body: Texto do corpo (máx 1024 chars)
        sections: Lista de seções com items
        header: Texto do cabeçalho (opcional)
        button_text: Texto do botão (máx 20 chars)

    Returns:
        Dict conforme WhatsApp API spec
    """
    if not sections:
        raise ValueError("Sections cannot be empty")

    body = body.strip() if body else ""
    if len(body) > 1024:
        body = body[:1021] + "..."

    if not body:
        raise ValueError("Body cannot be empty")

    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": button_text[:20],
                "sections": sections,
            },
        },
    }

    if header:
        header = header.strip()[:60]
        payload["interactive"]["header"] = {"type": "text", "text": header}

    return payload


def build_reaction_payload(
    to: str,
    emoji: str,
    message_id: str,
) -> dict[str, Any]:
    """Constrói payload de reação com emoji.

    Args:
        to: Número WhatsApp
        emoji: Emoji para reação (ex: "👍")
        message_id: ID da mensagem anterior (para reação)

    Returns:
        Dict conforme WhatsApp API spec
    """
    # Validar emoji (deve ser single emoji)
    if not emoji or len(emoji.encode("utf-8")) > 4:
        emoji = "👍"

    return {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "reaction",
        "reaction": {
            "message_id": message_id,
            "emoji": emoji,
        },
    }


def build_sticker_payload(
    to: str,
    sticker_id: str,
) -> dict[str, Any]:
    """Constrói payload de sticker.

    Args:
        to: Número WhatsApp
        sticker_id: ID do sticker (ou URL)

    Returns:
        Dict conforme WhatsApp API spec
    """
    if not sticker_id:
        raise ValueError("Sticker ID cannot be empty")

    return {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "sticker",
        "sticker": {
            "link": sticker_id,  # Pode ser URL ou ID do Media
        },
    }


def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Sanitiza payload removendo PII para logging seguro.

    Mascareia:
    - Números de telefone (deixa últimos 4 dígitos)
    - Emails
    - Documentos

    Args:
        payload: Payload original (não modifica)

    Returns:
        Payload com campos sensíveis mascarados
    """
    import copy

    sanitized = copy.deepcopy(payload)

    # Mascarar número "to"
    if "to" in sanitized:
        phone = str(sanitized["to"])
        if len(phone) > 4:
            sanitized["to"] = f"***{phone[-4:]}"

    # Mascarar texto (se contiver email/documento)
    text_fields = [
        ("text", "body"),
        ("interactive", "body", "text"),
        ("interactive", "header", "text"),
        ("interactive", "footer", "text"),
    ]

    for path in text_fields:
        try:
            current = sanitized
            for key in path[:-1]:
                if isinstance(current, dict):
                    current = current.get(key)
                else:
                    current = None
                    break

            if current and isinstance(current, dict):
                final_key = path[-1]
                if final_key in current:
                    text = current[final_key]
                    current[final_key] = _mask_sensitive_text(text)
        except (KeyError, TypeError, AttributeError):
            pass  # Field not present, skip

    return sanitized


def _mask_sensitive_text(text: str) -> str:
    """Mascareia email, CPF, telefone em texto."""
    # Email pattern
    text = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL]", text)

    # CPF/CNPJ-like patterns (11 dígitos)
    text = re.sub(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", "[DOCUMENT]", text)

    # Telefone pattern (11 dígitos)
    text = re.sub(r"\(\d{2}\)\s?9?\d{4}-\d{4}", "[PHONE]", text)

    return text


def validate_payload(payload: dict[str, Any]) -> tuple[bool, str]:
    """Valida payload conforme WhatsApp API spec.

    Args:
        payload: Payload a validar

    Returns:
        Tuple (is_valid, error_message)
    """
    if not payload or not isinstance(payload, dict):
        return False, "Payload must be a non-empty dict"

    if payload.get("messaging_product") != "whatsapp":
        return False, "messaging_product must be 'whatsapp'"

    if "to" not in payload:
        return False, "Missing required field: 'to'"

    if "type" not in payload:
        return False, "Missing required field: 'type'"

    message_type = payload.get("type")
    if message_type not in ("text", "interactive", "reaction", "sticker"):
        return False, f"Invalid message type: {message_type}"

    # Type-specific validation
    if message_type == "text":
        if "text" not in payload or "body" not in payload.get("text", {}):
            return False, "Text message must have text.body"

    elif message_type == "interactive":
        if "interactive" not in payload:
            return False, "Interactive message must have interactive field"

    elif message_type == "reaction":
        if "reaction" not in payload:
            return False, "Reaction must have reaction field"

    elif message_type == "sticker":
        if "sticker" not in payload:
            return False, "Sticker must have sticker field"

    return True, "OK"
