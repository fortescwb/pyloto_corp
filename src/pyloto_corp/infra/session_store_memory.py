"""Implementação de SessionStore em memória (apenas dev/testes)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pyloto_corp.infra.session_contract import SessionStore
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.application.session import SessionState

logger: logging.Logger = get_logger(__name__)


class InMemorySessionStore(SessionStore):
    """Armazenamento em memória (não usar em produção)."""

    def __init__(self) -> None:
        self._sessions: dict[str, tuple[SessionState, float]] = {}

    def save(self, session: SessionState, ttl_seconds: int = 7200) -> None:
        expire_at = datetime.now(tz=UTC).timestamp() + ttl_seconds
        self._sessions[session.session_id] = (session, expire_at)
        logger.debug(
            "Session saved (in-memory)",
            extra={"session_id": session.session_id[:8] + "...", "ttl_seconds": ttl_seconds},
        )

    def load(self, session_id: str) -> SessionState | None:
        if session_id not in self._sessions:
            logger.debug(
                "Session not found (in-memory)",
                extra={"session_id": session_id[:8] + "..."},
            )
            return None

        session, expire_at = self._sessions[session_id]
        now = datetime.now(tz=UTC).timestamp()

        if now > expire_at:
            del self._sessions[session_id]
            logger.debug(
                "Session expired (in-memory)",
                extra={"session_id": session_id[:8] + "..."},
            )
            return None

        logger.debug(
            "Session loaded (in-memory)", extra={"session_id": session_id[:8] + "..."}
        )
        return session

    def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.debug(
                "Session deleted (in-memory)",
                extra={"session_id": session_id[:8] + "..."},
            )
            return True
        return False

    def exists(self, session_id: str) -> bool:
        return self.load(session_id) is not None
