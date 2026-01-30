"""Helpers puros para operações na SessionState.

Funções testáveis relacionadas a histórico temporal de mensagens.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _to_datetime(ts: str | int | None) -> datetime | None:
    if ts is None:
        return None
    try:
        # Meta envia timestamp como string de segundos
        t = int(ts)
        return datetime.fromtimestamp(t, tz=UTC)
    except Exception:
        try:
            return datetime.fromisoformat(str(ts))
        except Exception:
            return None


def is_first_message_of_day(session: Any, message_timestamp: str | int | None) -> bool:
    """Retorna True se a mensagem é a primeira do dia na sessão.

    A função é pura (não faz IO) e usa apenas `session.message_history`.
    Usa janela de dia em UTC para consistência.
    """
    message_dt = _to_datetime(message_timestamp)
    if message_dt is None:
        # Sem timestamp confiável, considera primeira por segurança
        return True

    for rec in getattr(session, "message_history", []) or []:
        received = rec.get("received_at")
        if not received:
            continue
        rec_dt = _to_datetime(received)
        if rec_dt is None:
            continue
        if (
            rec_dt.year == message_dt.year
            and rec_dt.month == message_dt.month
            and rec_dt.day == message_dt.day
        ):
            return False

    return True


def append_received_event(session: Any, message_timestamp: str | int | None) -> None:
    """Adiciona um registro minimalista de recebimento na `session.message_history`.

    Registro mínimo: {"received_at": <isoformat UTC str>}.
    """
    message_dt = _to_datetime(message_timestamp)
    iso = message_dt.isoformat() if message_dt is not None else None
    entry: dict[str, Any] = {"received_at": iso}
    getattr(session, "message_history", []).append(entry)
