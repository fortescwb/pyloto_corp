"""Contrato Pydantic para geração de resposta via LLM #2."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from pyloto_corp.domain.enums import Intent
from pyloto_corp.domain.session.events import SessionEvent
from pyloto_corp.domain.session.states import SessionState


class ResponseGenerationRequest(BaseModel):
    """Input para LLM #2 — Response Generator."""

    event: SessionEvent
    """Evento detectado (do LLM #1)."""

    detected_intent: Intent
    """Intenção do usuário."""

    current_state: SessionState
    """Estado atual da sessão (saída do FSM dispatch)."""

    next_state: SessionState
    """Próximo estado proposto (saída do FSM dispatch)."""

    user_input: str
    """Mensagem original do usuário."""

    session_context: dict[str, Any] = Field(default_factory=dict)
    """Contexto adicional (lead profile, histórico)."""

    confidence_event: float = Field(..., ge=0.0, le=1.0)
    """Confiança do evento (do LLM #1)."""


class ResponseOption(BaseModel):
    """Uma opção de resposta (para listas/botões)."""

    id: str = Field(..., max_length=100)
    """ID único da opção."""

    title: str = Field(..., max_length=512)
    """Título exibido."""

    description: str | None = Field(None, max_length=1024)
    """Descrição adicional (opcional)."""


class ResponseGenerationResult(BaseModel):
    """Output de LLM #2 — resposta gerada."""

    text_content: str = Field(..., min_length=1, max_length=4096)
    """Conteúdo principal da resposta."""

    options: list[ResponseOption] = Field(default_factory=list)
    """Opções (se resposta tiver múltiplas escolhas)."""

    suggested_next_state: SessionState | None = None
    """Próximo estado sugerido pelo LLM (validado contra FSM)."""

    requires_human_review: bool = False
    """True se resposta requer revisão humana."""

    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    """Confiança da resposta gerada."""

    rationale: str | None = None
    """Justificativa da resposta (debug)."""
