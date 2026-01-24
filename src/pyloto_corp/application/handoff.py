"""Construção do handoff para humanos (esqueleto)."""

from __future__ import annotations

from pyloto_corp.domain.enums import Intent
from pyloto_corp.domain.models import ConversationHandoff, LeadProfile


def build_handoff(lead: LeadProfile, intents: list[Intent]) -> ConversationHandoff:
    """Cria o contrato de handoff a partir dos dados coletados.

    TODO: aplicar regras de qualificação e resumo estruturado.
    """

    return ConversationHandoff(
        intent_primary=intents[0] if intents else None,
        intents_detected=intents,
        resolved_intents=[],
        open_intents=intents[1:] if len(intents) > 1 else [],
        summary=None,
        requirements=[],
        deadline=None,
        routing=None,
        confidence=None,
        qualification_level=None,
        qualification_reasons=[],
    )
