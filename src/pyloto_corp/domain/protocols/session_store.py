"""Protocolos de domínio para persistência de sessão (sync e async)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyloto_corp.application.session import SessionState


class SessionStoreProtocol(ABC):
    """Contrato mínimo síncrono para armazenamento de SessionState."""

    @abstractmethod
    def save(self, session: SessionState, ttl_seconds: int = 7200) -> None: ...

    @abstractmethod
    def load(self, session_id: str) -> SessionState | None: ...

    @abstractmethod
    def delete(self, session_id: str) -> bool: ...

    @abstractmethod
    def exists(self, session_id: str) -> bool: ...


class AsyncSessionStoreProtocol(ABC):
    """Contrato mínimo assíncrono para armazenamento de SessionState."""

    @abstractmethod
    async def save(self, session: SessionState, ttl_seconds: int = 7200) -> None: ...

    @abstractmethod
    async def load(self, session_id: str) -> SessionState | None: ...

    @abstractmethod
    async def delete(self, session_id: str) -> bool: ...

    @abstractmethod
    async def exists(self, session_id: str) -> bool: ...
