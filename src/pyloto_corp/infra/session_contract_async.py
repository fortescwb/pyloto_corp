"""Contrato assíncrono de persistência de sessão.

Versão async-first do SessionStore para eliminar bloqueio de I/O.
Permite persistência não-bloqueante em Firestore, Redis, etc.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.application.session import SessionState

logger: logging.Logger = get_logger(__name__)


class AsyncSessionStoreError(Exception):
    """Erro ao persistir ou recuperar sessão de forma assíncrona."""

    pass


class AsyncSessionStore(ABC):
    """Contrato abstrato para armazenamento assíncrono de SessionState."""

    @abstractmethod
    async def save(self, session: SessionState, ttl_seconds: int = 7200) -> None:
        """Persiste sessão de forma assíncrona com TTL.

        Args:
            session: Sessão a persistir
            ttl_seconds: Time-to-live em segundos

        Raises:
            AsyncSessionStoreError: Se persistência falhar
        """
        ...

    @abstractmethod
    async def load(self, session_id: str) -> SessionState | None:
        """Carrega sessão por ID de forma assíncrona.

        Args:
            session_id: ID da sessão

        Returns:
            SessionState ou None se não encontrada
        """
        ...

    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        """Remove sessão do armazenamento de forma assíncrona.

        Args:
            session_id: ID da sessão a remover

        Returns:
            True se removida, False se não encontrada
        """
        ...

    @abstractmethod
    async def exists(self, session_id: str) -> bool:
        """Verifica se sessão existe e não expirou.

        Args:
            session_id: ID da sessão

        Returns:
            True se existe e válida
        """
        ...
