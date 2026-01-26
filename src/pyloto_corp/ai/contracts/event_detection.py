"""Contrato Pydantic para detecção de eventos via LLM #1."""

from __future__ import annotations

from pydantic import BaseModel, Field

from pyloto_corp.domain.enums import Intent
from pyloto_corp.domain.session.events import SessionEvent


class EventDetectionRequest(BaseModel):
    """Input para LLM #1 — Event Detector."""

    user_input: str = Field(..., min_length=1, max_length=4096)
    """Mensagem recebida do usuário."""

    session_history: list[str] = Field(default_factory=list)
    """Histórico de mensagens (últimas N)."""

    known_intent: Intent | None = None
    """Intenção já detectada (se houver)."""

    phone_number: str | None = None
    """Telefone do usuário (não expor em logs)."""


class EventDetectionResult(BaseModel):
    """Output de LLM #1 — resultado da classificação de evento."""

    event: SessionEvent
    """Evento disparador classificado."""

    detected_intent: Intent
    """Intenção detectada."""

    confidence: float = Field(..., ge=0.0, le=1.0)
    """Confiança do classificador (0.0 a 1.0)."""

    requires_followup: bool = False
    """True se requer validação adicional."""

    rationale: str | None = None
    """Justificativa da classificação (debug)."""
