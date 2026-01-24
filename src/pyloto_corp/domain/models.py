"""Modelos de domínio (contratos principais)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from pyloto_corp.domain.enums import Intent, Outcome


class LeadProfile(BaseModel):
    """Perfil básico do lead para handoff humano."""

    name: str | None = None
    phone: str | None = None
    city: str | None = None
    is_business: bool | None = None
    business_name: str | None = None
    role: str | None = None


class ConversationHandoff(BaseModel):
    """Contrato de handoff para continuidade humana."""

    intent_primary: Intent | None = None
    intents_detected: list[Intent] = Field(default_factory=list)
    resolved_intents: list[Intent] = Field(default_factory=list)
    open_intents: list[Intent] = Field(default_factory=list)
    summary: str | None = None
    requirements: list[str] = Field(default_factory=list)
    deadline: str | None = None
    routing: str | None = None
    confidence: float | None = None
    qualification_level: Literal["low", "medium", "high"] | None = None
    qualification_reasons: list[str] = Field(default_factory=list)


class SessionOutcome(BaseModel):
    """Resultado terminal da sessão."""

    outcome: Outcome
    reason: str | None = None
