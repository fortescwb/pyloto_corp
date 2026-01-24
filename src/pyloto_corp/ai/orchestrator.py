"""Orquestrador de IA (esqueleto)."""

from __future__ import annotations

from dataclasses import dataclass

from pyloto_corp.domain.enums import Intent, Outcome


@dataclass(slots=True)
class AIResponse:
    """Resposta do orquestrador de IA.

    TODO: integrar LLM e regras determinísticas.
    """

    reply_text: str | None = None
    outcome: Outcome | None = None
    intent: Intent | None = None


class AIOrchestrator:
    """Orquestra decisões de intenção e outcome."""

    def __init__(self) -> None:
        # TODO: carregar prompts e knowledge base.
        pass

    def handle_messages(self, _messages: list[object]) -> AIResponse:
        """Processa mensagens normalizadas e decide próximo passo."""

        # TODO: implementar pipeline de classificação + resposta.
        return AIResponse(outcome=Outcome.AWAITING_USER)
