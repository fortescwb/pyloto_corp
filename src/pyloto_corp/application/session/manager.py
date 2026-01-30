"""SessionManager e AsyncSessionManager — gerenciadores de ciclo de vida de sessão.

Centraliza operações de sessão (load/create, append, normalize, persist) que antes
estavam espalhadas nos pipelines. Mantém compatibilidade com logs e comportamentos
existentes.
"""

from __future__ import annotations

import logging
from typing import Any

from pyloto_corp.application.session.models import SessionState
from pyloto_corp.application.session_helpers import (
    append_received_event,
    is_first_message_of_day,
)
from pyloto_corp.config.settings import get_settings
from pyloto_corp.domain.conversation_state import ConversationState
from pyloto_corp.domain.fsm.initial_state import INITIAL_STATE
from pyloto_corp.observability.logging import get_logger


class SessionManager:
    """Gerencia ciclo de vida de sessão (load/create, append, normalize, persist).

    Implementa a API mínima requisitada pelo PR-06 e mantém compatibilidade
    com comportamento existente (logs, pruning, normalization).
    """

    def __init__(
        self,
        session_store: Any,
        logger: logging.Logger | None = None,
        settings: Any | None = None,
    ) -> None:
        self._sessions = session_store
        self._logger = logger or get_logger(__name__)
        self._settings = settings or get_settings()

    def get_or_create_session(self, message: Any, sender_phone: str | None = None) -> SessionState:
        """Recupera sessão existente (chat_id) ou cria nova, preservando logs atuais."""
        chat_id = getattr(message, "chat_id", None)

        if chat_id:
            session = self._sessions.load(chat_id)
            if session:
                self._logger.debug("Session loaded", extra={"session_id": chat_id[:8] + "..."})
                return session

        session_id = self._new_session_id()
        session = SessionState(session_id=session_id)
        self._logger.info(
            "New session created",
            extra={
                "session_id": session_id[:8] + "...",
                "chat_id": chat_id[:8] + "..." if chat_id else None,
            },
        )
        return session

    def _history_has_message_id(self, session: SessionState, message_id: str | None) -> bool:
        """Verifica se `message_id` já está presente no histórico de sessão.

        Não acessa dados sensíveis e usa apenas `session.message_history`.
        """
        if not message_id:
            return False
        for rec in getattr(session, "message_history", []) or []:
            if rec.get("message_id") == message_id:
                return True
        return False

    def append_user_message(
        self,
        session: SessionState,
        message: Any,
        correlation_id: str | None = None,
    ) -> bool:
        """Registra recebimento na sessão e retorna True se for primeira msg do dia.

        Agora é idempotente por `message_id`: se a mensagem já existe no histórico,
        não faz append novamente.
        """
        message_id = getattr(message, "message_id", None)
        had_any_received = any(rec.get("received_at") for rec in session.message_history)
        is_first = (not had_any_received) or is_first_message_of_day(
            session, getattr(message, "timestamp", None)
        )

        # Se já existe, não re-anexar
        if self._history_has_message_id(session, message_id):
            return is_first

        try:
            append_received_event(
                session,
                getattr(message, "timestamp", None),
                correlation_id=correlation_id,
                message_id=message_id,
            )
        except Exception:  # pragma: no cover - não falhar o fluxo por erro de append
            self._logger.warning("failed_to_append_received_event")

        return is_first

    def normalize_current_state(
        self, session: SessionState, correlation_id: str | None = None
    ) -> ConversationState:
        """Garante que `session.current_state` seja um `ConversationState` válido.

        Em caso de valor inválido, persiste a normalização (mesma semântica anterior)
        e emite log estruturado `invalid_state_normalized`.
        Retorna a instância de `ConversationState` atualizada.
        """
        try:
            return ConversationState(session.current_state)
        except Exception:
            session_id_full = getattr(session, "session_id", None)
            session_prefix = session_id_full[:8] if session_id_full else None
            self._logger.warning(
                "invalid_state_normalized",
                extra={
                    "event": "invalid_state_normalized",
                    "invalid_state_value": str(getattr(session, "current_state", None)),
                    "normalized_to": INITIAL_STATE.value,
                    "correlation_id": correlation_id,
                    "session_id": session_prefix,
                },
            )
            # Persist normalization to avoid later enum conversion errors
            session.current_state = INITIAL_STATE.value
            return INITIAL_STATE

    def persist(self, session: SessionState, correlation_id: str | None = None) -> None:
        """Persiste sessão via `session_store` com log amigável de erro."""
        try:
            self._sessions.save(session)
        except Exception as e:  # pragma: no cover - tratado nos pipelines
            self._logger.error(
                "Failed to save session",
                extra={"session_id": session.session_id[:8], "error": str(e)},
            )

    def prepare_for_processing(
        self, message: Any, sender_phone: str | None = None, correlation_id: str | None = None
    ) -> tuple[SessionState, bool]:
        """Prepara sessão para processamento.

        Encapsula: get_or_create + normalize. *Não* faz append do recebimento —
        isso é centralizado em `_orchestrate_and_save` para garantir ordem correta
        na decisão do prefixo do Otto (primeira do dia).

        Retorna: (session, False)
        """
        session = self.get_or_create_session(message, sender_phone)
        self.normalize_current_state(session, correlation_id)
        return session, False

    def finalize_after_orchestration(
        self, session: SessionState, outcome: Any, correlation_id: str | None = None
    ) -> None:
        """Finaliza session após orquestração: persist + tracking.

        Chamado após os LLMs decidirem tudo (state, response, etc).
        """
        session.outcome = outcome
        self.persist(session, correlation_id)

    def _new_session_id(self) -> str:
        # Evitar import circular no topo
        from pyloto_corp.utils.ids import new_session_id

        return new_session_id()


class AsyncSessionManager:
    """Versão assíncrona do SessionManager para pipelines async.

    Implementa métodos `async` paralelos ao `SessionManager` para interoperar com
    `AsyncSessionStoreProtocol`.
    """

    def __init__(
        self,
        async_session_store: Any,
        logger: logging.Logger | None = None,
        settings: Any | None = None,
    ) -> None:
        self._async_sessions = async_session_store
        self._logger = logger or get_logger(__name__)
        self._settings = settings or get_settings()

    async def get_or_create_session(
        self,
        message: Any,
        sender_phone: str | None = None,
    ) -> SessionState:
        chat_id = getattr(message, "chat_id", None)

        if chat_id:
            session = await self._async_sessions.load(chat_id)
            if session:
                self._logger.debug(
                    "Session loaded",
                    extra={"session_id": chat_id[:8] + "..."},
                )
                return session

        session = SessionState(session_id=self._new_session_id())
        self._logger.info(
            "New session created",
            extra={
                "session_id": session.session_id[:8] + "...",
                "chat_id": chat_id[:8] + "..." if chat_id else None,
            },
        )
        return session

    async def append_user_message(
        self,
        session: SessionState,
        message: Any,
        correlation_id: str | None = None,
    ) -> bool:
        from pyloto_corp.application.session_helpers import (
            append_received_event as _append,
        )
        from pyloto_corp.application.session_helpers import (
            is_first_message_of_day as _is_first,
        )

        message_id = getattr(message, "message_id", None)
        had_any_received = any(rec.get("received_at") for rec in session.message_history)
        is_first = (not had_any_received) or _is_first(session, getattr(message, "timestamp", None))

        # Não anexar se message_id já estiver no histórico
        if message_id:
            already = any(
                rec.get("message_id") == message_id for rec in session.message_history
            )
            if already:
                return is_first

        try:
            _append(
                session,
                getattr(message, "timestamp", None),
                correlation_id=correlation_id,
                message_id=message_id,
            )
        except Exception:  # pragma: no cover - não falhar o fluxo por erro de append
            self._logger.warning("failed_to_append_received_event")

        return is_first

    async def normalize_current_state(
        self, session: SessionState, correlation_id: str | None = None
    ) -> ConversationState:
        try:
            return ConversationState(session.current_state)
        except Exception:
            session_id_full = getattr(session, "session_id", None)
            session_prefix = session_id_full[:8] if session_id_full else None
            self._logger.warning(
                "invalid_state_normalized",
                extra={
                    "event": "invalid_state_normalized",
                    "invalid_state_value": str(getattr(session, "current_state", None)),
                    "normalized_to": INITIAL_STATE.value,
                    "correlation_id": correlation_id,
                    "session_id": session_prefix,
                },
            )
            session.current_state = INITIAL_STATE.value
            return INITIAL_STATE

    async def persist(self, session: SessionState, correlation_id: str | None = None) -> None:
        try:
            await self._async_sessions.save(session)
        except Exception as e:  # pragma: no cover - tratado nos pipelines
            self._logger.error(
                "Failed to save session",
                extra={"session_id": session.session_id[:8], "error": str(e)},
            )

    def _new_session_id(self) -> str:
        from pyloto_corp.utils.ids import new_session_id

        return new_session_id()
