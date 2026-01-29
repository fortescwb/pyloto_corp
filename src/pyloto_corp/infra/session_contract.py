"""Contrato de persistência de sessão (SessionStore).

Separado para manter SRP e permitir reuso entre implementações.
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import TYPE_CHECKING

from pyloto_corp.domain.protocols.session_store import SessionStoreProtocol
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.application.session import SessionState

logger: logging.Logger = get_logger(__name__)


class SessionStoreError(Exception):
    """Erro ao persistir ou recuperar sessão."""

    pass


class SessionStore(SessionStoreProtocol):
    """Contrato abstrato para armazenamento de SessionState."""

    @abstractmethod
    def save(self, session: SessionState, ttl_seconds: int = 7200) -> None:
        """Persiste a sessão com TTL."""
        ...

    @abstractmethod
    def load(self, session_id: str) -> SessionState | None:
        """Carrega sessão por ID."""
        ...

    @abstractmethod
    def delete(self, session_id: str) -> bool:
        """Remove sessão do armazenamento."""
        ...

    @abstractmethod
    def exists(self, session_id: str) -> bool:
        """Verifica se sessão existe e não expirou."""
        ...
