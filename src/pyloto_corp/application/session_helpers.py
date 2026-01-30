"""Helpers puros para operações na SessionState.

Este módulo existe ao lado de `session.py` (que é um módulo único) para evitar
criar um pacote `session/` que quebraria compatibilidade com imports existentes.
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


def append_received_event(
    session: Any,
    message_timestamp: str | int | None,
    correlation_id: str | None = None,
    message_id: str | None = None,
) -> None:
    """Adiciona um registro minimalista de recebimento na `session.message_history`.

    Registro mínimo: {"received_at": <isoformat UTC str>}.
    Armazena também `message_id` quando fornecido para permitir idempotência por mensagem.

    Implementa poda segura quando o tamanho excede
    `Settings.SESSION_MESSAGE_HISTORY_MAX_ENTRIES` (mantendo as N entradas mais recentes).
    Em caso de poda, emite log estruturado sem PII.
    """
    from pyloto_corp.config.settings import get_settings
    from pyloto_corp.observability.logging import get_logger

    logger = get_logger(__name__)

    message_dt = _to_datetime(message_timestamp)
    iso = message_dt.isoformat() if message_dt is not None else None
    entry: dict[str, Any] = {"received_at": iso}
    if message_id is not None:
        entry["message_id"] = message_id

    history = getattr(session, "message_history", None)
    if history is None:
        session.message_history = []
        history = session.message_history

    history.append(entry)

    # Poda determinística (mantém as últimas N entradas)
    settings = get_settings()
    max_entries = int(getattr(settings, "SESSION_MESSAGE_HISTORY_MAX_ENTRIES", 200))
    previous_len = len(history)
    if previous_len > max_entries:
        # manter apenas as N mais recentes (inclui a entrada recém-adicionada)
        new_history = history[-max_entries:]
        session.message_history = new_history
        new_len = len(session.message_history)
        # Emitir log estruturado, sem PII
        logger.info(
            "session_history_pruned",
            extra={
                "session_history_pruned": True,
                "max_entries": max_entries,
                "previous_len": previous_len,
                "new_len": new_len,
                "correlation_id": correlation_id,
            },
        )
