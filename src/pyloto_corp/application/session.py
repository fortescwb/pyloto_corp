"""Gerenciamento de sessão (esqueleto)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from pyloto_corp.domain.enums import Outcome
from pyloto_corp.domain.intent_queue import IntentQueue
from pyloto_corp.domain.models import LeadProfile


@dataclass(slots=True)
class SessionState:
    """Estado mínimo da sessão em memória.

    TODO: persistir em storage externo (Redis/DB) para Cloud Run stateless.
    """

    session_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    lead_profile: LeadProfile = field(default_factory=LeadProfile)
    intent_queue: IntentQueue = field(default_factory=IntentQueue)
    outcome: Outcome | None = None
