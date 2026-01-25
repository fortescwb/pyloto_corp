"""Implementação de SessionStore usando Firestore (produção)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from pyloto_corp.infra.session_contract import SessionStore, SessionStoreError
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.application.session import SessionState

logger: logging.Logger = get_logger(__name__)


def _parse_expire_at(raw_expire_at: datetime | str | None) -> datetime | None:
    if raw_expire_at is None:
        return None

    if isinstance(raw_expire_at, datetime):
        return raw_expire_at

    try:
        normalized = raw_expire_at.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except Exception:  # pragma: no cover - defensive parse
        return None


class FirestoreSessionStore(SessionStore):
    """Armazenamento de sessão em Firestore.

    Coleção padrão: sessions/{session_id}
    TTL: campo _ttl_expire_at respeitado pela política do Firestore
    """

    def __init__(self, firestore_client: object, collection: str = "sessions"):
        self._client = firestore_client
        self._collection = collection

    def save(self, session: SessionState, ttl_seconds: int = 7200) -> None:
        doc_ref = self._client.collection(self._collection).document(session.session_id)
        expire_at = datetime.now(tz=UTC) + timedelta(seconds=ttl_seconds)

        try:
            payload = session.model_dump(mode="json")
            payload["_ttl_expire_at"] = expire_at
            doc_ref.set(payload)
            logger.debug(
                "Session saved (Firestore)",
                extra={"session_id": session.session_id[:8] + "...", "ttl_seconds": ttl_seconds},
            )
        except Exception as e:  # pragma: no cover - log + wrap
            logger.error(
                "Failed to save session to Firestore",
                extra={"session_id": session.session_id[:8] + "...", "error": str(e)},
            )
            raise SessionStoreError(f"Firestore save failed: {e}") from e

    def load(self, session_id: str) -> SessionState | None:
        doc_ref = self._client.collection(self._collection).document(session_id)

        try:
            doc = doc_ref.get()
            if not doc.exists:
                logger.debug(
                    "Session not found (Firestore)", extra={"session_id": session_id[:8] + "..."}
                )
                return None

            data = doc.to_dict() or {}
            expire_at = _parse_expire_at(data.pop("_ttl_expire_at", None))
            if expire_at and datetime.now(tz=UTC) > expire_at:
                logger.debug(
                    "Session expired (Firestore)", extra={"session_id": session_id[:8] + "..."}
                )
                doc_ref.delete()
                return None

            from pyloto_corp.application.session import SessionState

            session = SessionState.model_validate(data)
            logger.debug(
                "Session loaded (Firestore)", extra={"session_id": session_id[:8] + "..."}
            )
            return session
        except Exception as e:  # pragma: no cover - log + wrap
            logger.error(
                "Failed to load session from Firestore",
                extra={"session_id": session_id[:8] + "...", "error": str(e)},
            )
            return None

    def delete(self, session_id: str) -> bool:
        doc_ref = self._client.collection(self._collection).document(session_id)

        try:
            doc_ref.delete()
            logger.debug(
                "Session deleted (Firestore)", extra={"session_id": session_id[:8] + "..."}
            )
            return True
        except Exception as e:  # pragma: no cover - log best effort
            logger.error(
                "Failed to delete session from Firestore",
                extra={"session_id": session_id[:8] + "...", "error": str(e)},
            )
            return False

    def exists(self, session_id: str) -> bool:
        doc_ref = self._client.collection(self._collection).document(session_id)

        try:
            doc = doc_ref.get()
            if not doc.exists:
                return False

            data = doc.to_dict() or {}
            expire_at = _parse_expire_at(data.get("_ttl_expire_at"))
            return not (expire_at and datetime.now(tz=UTC) > expire_at)
        except Exception as e:  # pragma: no cover - log best effort
            logger.error(
                "Failed to check session existence in Firestore",
                extra={"session_id": session_id[:8] + "...", "error": str(e)},
            )
            return False
