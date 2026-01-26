"""Contrato Pydantic para seleção de tipo de mensagem via LLM #3."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from pyloto_corp.domain.enums import MessageType


class MessageTypeSelectionRequest(BaseModel):
    """Input para LLM #3 — Message Type Selector."""

    text_content: str = Field(..., min_length=1, max_length=4096)
    """Conteúdo da resposta (do LLM #2)."""

    options: list[dict[str, str]] = Field(default_factory=list)
    """Opções (se houver)."""

    intent_type: str | None = None
    """Tipo de intent detectado."""

    user_preference: str | None = None
    """Preferência do usuário (se houver)."""

    turn_count: int = 0
    """Número de turnos nesta sessão."""


class MessageTypeSelectionResult(BaseModel):
    """Output de LLM #3 — tipo de mensagem selecionado."""

    message_type: MessageType
    """Tipo de mensagem a usar (TEXT, IMAGE, INTERACTIVE, etc.)."""

    parameters: dict[str, Any] = Field(default_factory=dict)
    """Parâmetros específicos do tipo de mensagem."""

    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    """Confiança da seleção."""

    rationale: str | None = None
    """Justificativa da escolha (debug)."""

    fallback: bool = False
    """True se usou fallback heurístico."""
