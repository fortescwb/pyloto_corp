"""Models de sessão — SessionState.

SessionState é a unidade atômica de interação com um cliente.
- Uma sessão = um session_id único
- Uma sessão = exatamente um outcome terminal
- Sessões são persistidas em Redis/Firestore para Cloud Run stateless
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from pyloto_corp.domain.enums import Outcome
from pyloto_corp.domain.intent_queue import IntentQueue
from pyloto_corp.domain.models import LeadProfile


# Avoid importing INITIAL_STATE at class scope (pydantic will treat non-annotated names as fields).
def _initial_state_value() -> str:
    from pyloto_corp.domain.fsm.initial_state import INITIAL_STATE

    return INITIAL_STATE.value


class SessionState(BaseModel):
    """Estado completo da sessão com suporte a persistência.

    Responsabilidades:
    - Rastrear intenções do cliente
    - Manter lead profile em construção
    - Registrar outcome terminal
    - Serializável para Redis/Firestore
    """

    session_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    lead_profile: LeadProfile = Field(default_factory=LeadProfile)
    intent_queue: IntentQueue = Field(default_factory=IntentQueue)
    outcome: Outcome | None = None

    # Campos adicionados para suporte ao pipeline v2 (FSM + LLM)
    current_state: str = Field(default_factory=_initial_state_value)
    message_history: list[dict[str, Any]] = Field(default_factory=list)
