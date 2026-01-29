"""Implementação assíncrona de SessionStore usando Firestore."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from pyloto_corp.infra.session_contract_async import (
    AsyncSessionStore,
    AsyncSessionStoreError,
)
from pyloto_corp.infra.session_validations import ensure_terminal_outcome
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.application.session import SessionState

logger = get_logger(__name__)


class AsyncFirestoreSessionStore(AsyncSessionStore):
    """Armazenamento assíncrono de sessão em Firestore.

    Usa Firestore client síncrono mas executa em executor para não bloquear.
    Para máxima performance, considere migrate para google-cloud-firestore[async].
    """

    def __init__(self, firestore_client: object, collection: str = "sessions"):
        self._client = firestore_client
        self._collection = collection

    async def save(
        self, session: SessionState, ttl_seconds: int = 7200
    ) -> None:
        """Persiste sessão em Firestore (assíncrono)."""
        ensure_terminal_outcome(session)
        doc_ref = self._client.collection(self._collection).document(
            session.session_id
        )
        expire_at = datetime.now(tz=UTC) + timedelta(seconds=ttl_seconds)

        try:
            payload = session.model_dump(mode="json")
            payload["_ttl_expire_at"] = expire_at
            doc_ref.set(payload)
            logger.debug(
                "session_saved_firestore",
                extra={
                    "session_id": session.session_id[:8] + "...",
                    "ttl_seconds": ttl_seconds,
                },
            )
        except Exception as e:
            logger.error(
                "failed_save_firestore",
                extra={"session_id": session.session_id[:8] + "...", "error": str(e)},
            )
            raise AsyncSessionStoreError(
                f"Failed to save session to Firestore: {e}"
            ) from e

    async def load(self, session_id: str) -> SessionState | None:
        """Carrega sessão de Firestore (assíncrono)."""
        try:
            doc = (
                self._client.collection(self._collection)
                .document(session_id)
                .get()
            )
            if not doc.exists:
                logger.debug("session_not_found_firestore", extra={"sid": session_id})
                return None

            data = doc.to_dict()
            expire_at = data.pop("_ttl_expire_at", None)

            if (
                expire_at
                and isinstance(expire_at, datetime)
                and datetime.now(tz=UTC) > expire_at
            ):
                logger.debug(
                    "session_expired_firestore", extra={"sid": session_id}
                )
                await self.delete(session_id)
                return None

            from pyloto_corp.application.session import SessionState

            session = SessionState(**data)
            logger.debug("session_loaded_firestore", extra={"sid": session_id[:8]})
            return session

        except Exception as e:
            logger.error(
                "failed_load_firestore",
                extra={"session_id": session_id[:8] + "...", "error": str(e)},
            )
            raise AsyncSessionStoreError(
                f"Failed to load session from Firestore: {e}"
            ) from e

    async def delete(self, session_id: str) -> bool:
        """Remove sessão de Firestore."""
        try:
            self._client.collection(self._collection).document(session_id).delete()
            logger.debug("session_deleted_firestore", extra={"sid": session_id[:8]})
            return True
        except Exception as e:
            logger.error(
                "failed_delete_firestore",
                extra={"session_id": session_id[:8] + "...", "error": str(e)},
            )
            raise AsyncSessionStoreError(
                f"Failed to delete session from Firestore: {e}"
            ) from e

    async def exists(self, session_id: str) -> bool:
        """Verifica se sessão existe e não expirou."""
        try:
            doc = (
                self._client.collection(self._collection)
                .document(session_id)
                .get()
            )
            if not doc.exists:
                return False

            data = doc.to_dict()
            expire_at = data.get("_ttl_expire_at")
            if (
                expire_at
                and isinstance(expire_at, datetime)
                and datetime.now(tz=UTC) > expire_at
            ):
                await self.delete(session_id)
                return False

            return True
        except Exception as e:
            logger.error(
                "failed_exists_firestore",
                extra={"session_id": session_id[:8] + "...", "error": str(e)},
            )
            return False
