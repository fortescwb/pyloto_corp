"""Persistência de sessão — armazenamento em Redis/Firestore.

Contratos e implementações para persistência de SessionState com suporte
a timeouts, isolamento por sessão e zero vazamento de contexto entre sessões.

Conforme Funcionamento.md § 3.4 e regras_e_padroes.md.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.application.session import SessionState
    from pyloto_corp.infra.dedupe import DedupeStore

logger: logging.Logger = get_logger(__name__)


class SessionStoreError(Exception):
    """Erro ao persistir ou recuperar sessão."""

    pass


class SessionStore(ABC):
    """Contrato abstrato para armazenamento de SessionState.

    Responsabilidades:
    - Persistir sessão com TTL
    - Recuperar sessão por session_id
    - Aplicar timeout de inatividade
    - Garantir isolamento entre sessões
    """

    @abstractmethod
    def save(
        self, session: SessionState, ttl_seconds: int = 7200
    ) -> None:
        """Persiste a sessão com TTL.

        Args:
            session: SessionState a persistir
            ttl_seconds: Time-to-live em segundos (padrão: 2h)

        Raises:
            SessionStoreError: Em caso de falha de persistência
        """
        ...

    @abstractmethod
    def load(self, session_id: str) -> SessionState | None:
        """Carrega sessão por ID.

        Args:
            session_id: ID único da sessão

        Returns:
            SessionState se encontrada e não expirada, None caso contrário
        """
        ...

    @abstractmethod
    def delete(self, session_id: str) -> bool:
        """Remove sessão do armazenamento.

        Args:
            session_id: ID único da sessão

        Returns:
            True se removida, False se não existia
        """
        ...

    @abstractmethod
    def exists(self, session_id: str) -> bool:
        """Verifica se sessão existe e não expirou.

        Args:
            session_id: ID único da sessão

        Returns:
            True se existe e está ativa
        """
        ...


class InMemorySessionStore(SessionStore):
    """Armazenamento em memória para desenvolvimento e testes.

    ⚠️ Não usar em produção!
    - Não persiste entre restarts
    - Não funciona com múltiplas instâncias Cloud Run
    - Útil apenas para desenvolvimento local
    """

    def __init__(self) -> None:
        self._sessions: dict[str, tuple[SessionState, float]] = {}

    def save(self, session: SessionState, ttl_seconds: int = 7200) -> None:
        """Armazena em memória com timestamp de expiração."""
        expire_at = datetime.now(tz=UTC).timestamp() + ttl_seconds
        self._sessions[session.session_id] = (session, expire_at)
        logger.debug(
            "Session saved (in-memory)",
            extra={
                "session_id": session.session_id[:8] + "...",
                "ttl_seconds": ttl_seconds,
            },
        )

    def load(self, session_id: str) -> SessionState | None:
        """Carrega sessão se não expirou."""
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
            "Session loaded (in-memory)",
            extra={"session_id": session_id[:8] + "..."},
        )
        return session

    def delete(self, session_id: str) -> bool:
        """Remove sessão da memória."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.debug(
                "Session deleted (in-memory)",
                extra={"session_id": session_id[:8] + "..."},
            )
            return True
        return False

    def exists(self, session_id: str) -> bool:
        """Verifica se sessão está ativa."""
        return self.load(session_id) is not None


class RedisSessionStore(SessionStore):
    """Armazenamento em Redis (Upstash) para produção.

    Características:
    - TTL nativo de Redis
    - Atomicidade de operações
    - Escalável para múltiplas instâncias
    """

    def __init__(self, redis_client: object) -> None:
        self._redis = redis_client

    def save(self, session: SessionState, ttl_seconds: int = 7200) -> None:
        """Persiste sessão em Redis com TTL."""
        key = f"session:{session.session_id}"
        payload = session.model_dump_json()

        try:
            self._redis.setex(key, ttl_seconds, payload)
            logger.debug(
                "Session saved (Redis)",
                extra={
                    "session_id": session.session_id[:8] + "...",
                    "ttl_seconds": ttl_seconds,
                },
            )
        except Exception as e:
            logger.error(
                "Failed to save session to Redis",
                extra={
                    "session_id": session.session_id[:8] + "...",
                    "error": str(e),
                },
            )
            raise SessionStoreError(f"Redis save failed: {e}") from e

    def load(self, session_id: str) -> SessionState | None:
        """Carrega sessão de Redis."""
        key = f"session:{session_id}"

        try:
            payload = self._redis.get(key)
            if not payload:
                logger.debug(
                    "Session not found (Redis)",
                    extra={"session_id": session_id[:8] + "..."},
                )
                return None

            # Se for bytes (redis-py), decodificar
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8")

            from pyloto_corp.application.session import SessionState

            session = SessionState.model_validate_json(payload)
            logger.debug(
                "Session loaded (Redis)",
                extra={"session_id": session_id[:8] + "..."},
            )
            return session
        except Exception as e:
            logger.error(
                "Failed to load session from Redis",
                extra={
                    "session_id": session_id[:8] + "...",
                    "error": str(e),
                },
            )
            return None

    def delete(self, session_id: str) -> bool:
        """Remove sessão de Redis."""
        key = f"session:{session_id}"

        try:
            deleted = self._redis.delete(key)
            if deleted:
                logger.debug(
                    "Session deleted (Redis)",
                    extra={"session_id": session_id[:8] + "..."},
                )
            return bool(deleted)
        except Exception as e:
            logger.error(
                "Failed to delete session from Redis",
                extra={
                    "session_id": session_id[:8] + "...",
                    "error": str(e),
                },
            )
            return False

    def exists(self, session_id: str) -> bool:
        """Verifica se sessão existe em Redis."""
        key = f"session:{session_id}"

        try:
            return bool(self._redis.exists(key))
        except Exception as e:
            logger.error(
                "Failed to check session existence in Redis",
                extra={
                    "session_id": session_id[:8] + "...",
                    "error": str(e),
                },
            )
            return False


class FirestoreSessionStore(SessionStore):
    """Armazenamento em Firestore para produção.

    Coleção: sessions/{session_id}
    Características:
    - TTL via Firestore TTL policy
    - Transacional
    - Auditável via Firestore logs
    """

    def __init__(self, firestore_client: object, collection: str = "sessions"):
        self._client = firestore_client
        self._collection = collection

    def save(self, session: SessionState, ttl_seconds: int = 7200) -> None:
        """Persiste sessão em Firestore com TTL."""
        doc_ref = self._client.collection(self._collection).document(
            session.session_id
        )
        expire_at = datetime.now(tz=UTC) + timedelta(seconds=ttl_seconds)

        try:
            payload = session.model_dump(mode="json")
            payload["_ttl_expire_at"] = expire_at
            doc_ref.set(payload)
            logger.debug(
                "Session saved (Firestore)",
                extra={
                    "session_id": session.session_id[:8] + "...",
                    "ttl_seconds": ttl_seconds,
                },
            )
        except Exception as e:
            logger.error(
                "Failed to save session to Firestore",
                extra={
                    "session_id": session.session_id[:8] + "...",
                    "error": str(e),
                },
            )
            raise SessionStoreError(f"Firestore save failed: {e}") from e

    def load(self, session_id: str) -> SessionState | None:
        """Carrega sessão de Firestore."""
        doc_ref = self._client.collection(self._collection).document(
            session_id
        )

        try:
            doc = doc_ref.get()
            if not doc.exists:
                logger.debug(
                    "Session not found (Firestore)",
                    extra={"session_id": session_id[:8] + "..."},
                )
                return None

            data = doc.to_dict()
            if not data:
                return None

            # Verificar expiração TTL
            expire_at = data.pop("_ttl_expire_at", None)
            if expire_at:
                if isinstance(expire_at, str):
                    from dateutil.parser import isoparse

                    expire_at = isoparse(expire_at)
                if datetime.now(tz=UTC) > expire_at:
                    logger.debug(
                        "Session expired (Firestore)",
                        extra={"session_id": session_id[:8] + "..."},
                    )
                    doc_ref.delete()
                    return None

            from pyloto_corp.application.session import SessionState

            session = SessionState.model_validate(data)
            logger.debug(
                "Session loaded (Firestore)",
                extra={"session_id": session_id[:8] + "..."},
            )
            return session
        except Exception as e:
            logger.error(
                "Failed to load session from Firestore",
                extra={
                    "session_id": session_id[:8] + "...",
                    "error": str(e),
                },
            )
            return None

    def delete(self, session_id: str) -> bool:
        """Remove sessão de Firestore."""
        doc_ref = self._client.collection(self._collection).document(
            session_id
        )

        try:
            doc_ref.delete()
            logger.debug(
                "Session deleted (Firestore)",
                extra={"session_id": session_id[:8] + "..."},
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to delete session from Firestore",
                extra={
                    "session_id": session_id[:8] + "...",
                    "error": str(e),
                },
            )
            return False

    def exists(self, session_id: str) -> bool:
        """Verifica se sessão existe em Firestore."""
        doc_ref = self._client.collection(self._collection).document(
            session_id
        )

        try:
            doc = doc_ref.get()
            if not doc.exists:
                return False

            data = doc.to_dict()
            expire_at = data.get("_ttl_expire_at")
            if expire_at:
                if isinstance(expire_at, str):
                    from dateutil.parser import isoparse

                    expire_at = isoparse(expire_at)
                if datetime.now(tz=UTC) > expire_at:
                    return False

            return True
        except Exception as e:
            logger.error(
                "Failed to check session existence in Firestore",
                extra={
                    "session_id": session_id[:8] + "...",
                    "error": str(e),
                },
            )
            return False
