from __future__ import annotations

from typing import Any


def is_valid_message_data(message: dict[str, Any]) -> bool:
    """Valida shape mínimo necessário para seguir com normalização."""
    if not isinstance(message, dict):
        return False

    message_id = message.get("message_id")
    return bool(message_id)
