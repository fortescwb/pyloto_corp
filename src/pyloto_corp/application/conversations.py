"""Casos de uso para histórico de conversas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pyloto_corp.domain.conversations import (
    AppendResult,
    ConversationMessage,
    ConversationStore,
    Page,
)
from pyloto_corp.observability.logging import get_logger
from pyloto_corp.utils.ids import derive_user_key

logger = get_logger(__name__)

TEXT_MAX_LEN = 4000
TRUNCATION_MARKER = "…[truncated]"


def sanitize_text(text: str) -> str:
    """Sanitiza o texto para armazenamento.

    Regras:
    - strip nas extremidades
    - manter quebras de linha
    - colapsar excesso de whitespace em cada linha
    - limitar tamanho a TEXT_MAX_LEN
    """

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    blank_streak = 0

    for raw_line in normalized.split("\n"):
        collapsed = " ".join(raw_line.split())
        if collapsed == "":
            blank_streak += 1
            if blank_streak > 1:
                continue
            lines.append("")
            continue

        blank_streak = 0
        lines.append(collapsed)

    normalized = "\n".join(lines).strip()

    if len(normalized) > TEXT_MAX_LEN:
        limit = TEXT_MAX_LEN - len(TRUNCATION_MARKER)
        normalized = f"{normalized[:limit]}{TRUNCATION_MARKER}"

    return normalized


def _build_conversation_message(
    phone_e164: str,
    pepper_secret: str,
    provider_message_id: str,
    direction: Literal["in", "out"],
    actor: Literal["USER", "PYLOTO", "HUMAN"],
    timestamp: datetime,
    text: str,
    correlation_id: str | None = None,
    intent: str | None = None,
    outcome: str | None = None,
    tenant_id: str | None = None,
    provider: Literal["whatsapp"] = "whatsapp",
    payload_ref: str | None = None,
) -> ConversationMessage:
    """Constrói mensagem normalizada pronta para persistência.

    Responsabilidades:
    - Derivar user_key
    - Sanitizar texto
    - Criar instância de ConversationMessage
    """

    user_key = derive_user_key(phone_e164, pepper_secret)
    sanitized_text = sanitize_text(text)

    return ConversationMessage(
        provider=provider,
        provider_message_id=provider_message_id,
        user_key=user_key,
        tenant_id=tenant_id,
        direction=direction,
        actor=actor,
        timestamp=timestamp,
        text=sanitized_text,
        correlation_id=correlation_id,
        intent=intent,
        outcome=outcome,
        payload_ref=payload_ref,
    )


@dataclass(slots=True)
class AppendMessageUseCase:
    """Caso de uso para append de mensagem no histórico."""

    store: ConversationStore
    pepper_secret: str

    def execute(
        self,
        *,
        phone_e164: str,
        provider_message_id: str,
        direction: Literal["in", "out"],
        actor: Literal["USER", "PYLOTO", "HUMAN"],
        timestamp: datetime,
        text: str,
        correlation_id: str | None = None,
        intent: str | None = None,
        outcome: str | None = None,
        tenant_id: str | None = None,
        provider: Literal["whatsapp"] = "whatsapp",
        payload_ref: str | None = None,
    ) -> AppendResult:
        """Aplica sanitização, deriva user_key e grava no store."""

        message = _build_conversation_message(
            phone_e164=phone_e164,
            pepper_secret=self.pepper_secret,
            provider_message_id=provider_message_id,
            direction=direction,
            actor=actor,
            timestamp=timestamp,
            text=text,
            correlation_id=correlation_id,
            intent=intent,
            outcome=outcome,
            tenant_id=tenant_id,
            provider=provider,
            payload_ref=payload_ref,
        )

        result = self.store.append_message(message)

        logger.info(
            "Conversation message appended",
            extra={
                "correlation_id": correlation_id,
                "user_key": message.user_key,
                "provider_message_id": provider_message_id,
                "direction": direction,
                "message_created": result.created,
            },
        )

        return result


@dataclass(slots=True)
class GetHistoryUseCase:
    """Caso de uso para busca paginada de histórico."""

    store: ConversationStore

    def execute(self, *, user_key: str, limit: int = 50, cursor: str | None = None) -> Page:
        """Retorna mensagens paginadas."""

        return self.store.get_messages(user_key=user_key, limit=limit, cursor=cursor)


def export_history_txt(user_key: str, page: Page) -> str:
    """Gera export TXT simples a partir de uma página de mensagens."""

    header = f"Histórico de mensagens user_key={user_key}"
    lines = [header]

    for msg in page.items:
        timestamp = msg.timestamp.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S %Z")
        lines.append(f"[{timestamp}] {msg.actor} - {msg.text}")

    return "\n".join(lines)
