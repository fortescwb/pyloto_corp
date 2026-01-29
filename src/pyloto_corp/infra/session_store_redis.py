"""Implementação de SessionStore usando Redis (produção)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pyloto_corp.infra.session_contract import SessionStore, SessionStoreError
from pyloto_corp.infra.session_validations import ensure_terminal_outcome
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.application.session import SessionState

logger: logging.Logger = get_logger(__name__)


class RedisSessionStore(SessionStore):
    """Armazenamento em Redis (Upstash) para produção."""

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    def save(self, session: SessionState, ttl_seconds: int = 7200) -> None:
        ensure_terminal_outcome(session)
        key = f"session:{session.session_id}"
        payload = session.model_dump_json()

        try:
            self._redis.setex(key, ttl_seconds, payload)
            logger.debug(
                "Session saved (Redis)",
                extra={"session_id": session.session_id[:8] + "...", "ttl_seconds": ttl_seconds},
            )
        except Exception as e:  # pragma: no cover - log + wrap
            logger.error(
                "Failed to save session to Redis",
                extra={"session_id": session.session_id[:8] + "...", "error": str(e)},
            )
            raise SessionStoreError(f"Redis save failed: {e}") from e

    def load(self, session_id: str) -> SessionState | None:
        key = f"session:{session_id}"

        try:
            payload = self._redis.get(key)
            if not payload:
                logger.debug(
                    "Session not found (Redis)", extra={"session_id": session_id[:8] + "..."}
                )
                return None

            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")

            from pyloto_corp.application.session import SessionState

            session = SessionState.model_validate_json(payload)
            logger.debug(
                "Session loaded (Redis)", extra={"session_id": session_id[:8] + "..."}
            )
            return session
        except Exception as e:  # pragma: no cover - log + wrap
            logger.error(
                "Failed to load session from Redis",
                extra={"session_id": session_id[:8] + "...", "error": str(e)},
            )
            return None

    def delete(self, session_id: str) -> bool:
        key = f"session:{session_id}"

        try:
            deleted = self._redis.delete(key)
            if deleted:
                logger.debug(
                    "Session deleted (Redis)", extra={"session_id": session_id[:8] + "..."}
                )
            return bool(deleted)
        except Exception as e:  # pragma: no cover - log best effort
            logger.error(
                "Failed to delete session from Redis",
                extra={"session_id": session_id[:8] + "...", "error": str(e)},
            )
            return False

    def exists(self, session_id: str) -> bool:
        key = f"session:{session_id}"

        try:
            return bool(self._redis.exists(key))
        except Exception as e:  # pragma: no cover - log best effort
            logger.error(
                "Failed to check session existence in Redis",
                extra={"session_id": session_id[:8] + "...", "error": str(e)},
            )
            return False

