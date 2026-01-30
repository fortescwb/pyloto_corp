"""Dedupe persistente em Firestore (set-if-not-exists).

Responsabilidade:
- Registrar eventos inbound de forma idempotente
- Operar em Cloud Run (stateless) com TTL configurável
- Fail-closed em staging/prod quando Firestore estiver indisponível
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from google.api_core import exceptions as gcp_exceptions
from google.cloud import firestore

from pyloto_corp.infra.dedupe import DedupeError, DedupeStore
from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)


class FirestoreDedupeStore(DedupeStore):
    """Implementação de dedupe usando Firestore."""

    def __init__(
        self,
        client: firestore.Client,
        *,
        collection: str = "inbound_dedupe",
        ttl_seconds: int = 604800,
        fail_closed: bool = True,
    ) -> None:
        self._client = client
        self._collection = collection
        self._ttl_seconds = ttl_seconds
        self._fail_closed = fail_closed

    def mark_if_new(self, key: str) -> bool:
        """Cria documento com ID=key; retorna False se já existia."""
        doc_ref = self._client.collection(self._collection).document(key)
        expires_at = datetime.now(UTC) + timedelta(seconds=self._ttl_seconds)

        try:
            doc_ref.create(
                {
                    "created_at": firestore.SERVER_TIMESTAMP,
                    "expires_at": expires_at,
                }
            )
            return True
        except (gcp_exceptions.Conflict, gcp_exceptions.AlreadyExists):
            return False
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "firestore_dedupe_error",
                extra={"operation": "mark_if_new", "error": type(exc).__name__},
            )
            if self._fail_closed:
                raise DedupeError(f"Falha ao gravar dedupe no Firestore: {exc}") from exc
            return True

    def is_duplicate(self, key: str) -> bool:
        """Retorna True se documento existe e ainda não expirou."""
        try:
            snapshot = self._client.collection(self._collection).document(key).get()
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "firestore_dedupe_error",
                extra={"operation": "is_duplicate", "error": type(exc).__name__},
            )
            if self._fail_closed:
                raise DedupeError(f"Falha ao consultar dedupe: {exc}") from exc
            return False

        if not snapshot.exists:
            return False

        data = snapshot.to_dict() or {}
        expires_at = data.get("expires_at")
        if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at and expires_at < datetime.now(UTC):
            self.clear(key)
            return False

        return True

    def clear(self, key: str) -> bool:
        """Remove documento (usado apenas em dev/testes)."""
        try:
            self._client.collection(self._collection).document(key).delete()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "firestore_dedupe_clear_failed",
                extra={"error": type(exc).__name__},
            )
            return False
