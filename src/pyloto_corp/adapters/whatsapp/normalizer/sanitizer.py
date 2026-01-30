from __future__ import annotations

from typing import Any


def sanitize_message_payload(message: dict[str, Any]) -> dict[str, Any]:
    """Sanitiza payload intermediário sem alterar comportamento atual."""
    if not isinstance(message, dict):
        return {}
    return message
