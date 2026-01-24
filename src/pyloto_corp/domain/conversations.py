"""Contratos de domínio para histórico de conversas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, Field


class ConversationHeader(BaseModel):
    """Cabeçalho da conversa por usuário."""

    user_key: str
    channel: Literal["whatsapp"]
    tenant_id: str | None = None
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime


class ConversationMessage(BaseModel):
    """Mensagem persistida no histórico."""

    provider: Literal["whatsapp"]
    provider_message_id: str
    user_key: str
    tenant_id: str | None = None
    direction: Literal["in", "out"]
    actor: Literal["USER", "PYLOTO", "HUMAN"]
    timestamp: datetime
    text: str
    correlation_id: str | None = None
    intent: str | None = None
    outcome: str | None = None
    payload_ref: str | None = None


class AppendResult(BaseModel):
    """Resultado de append com idempotência."""

    created: bool


class Page(BaseModel):
    """Página de resultados."""

    items: list[ConversationMessage] = Field(default_factory=list)
    next_cursor: str | None = None


class ConversationStore(Protocol):
    """Porta de armazenamento de conversas."""

    def append_message(self, message: ConversationMessage) -> AppendResult:
        """Insere mensagem no histórico com idempotência."""

    def get_messages(self, user_key: str, limit: int, cursor: str | None = None) -> Page:
        """Retorna mensagens paginadas."""

    def get_header(self, user_key: str) -> ConversationHeader | None:
        """Retorna o cabeçalho de conversa, se existir."""
