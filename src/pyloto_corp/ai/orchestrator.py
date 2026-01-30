"""Orquestrador de IA — classificação de intenção e decisão de outcome.

Responsabilidades:
- Classificar intenção primária da mensagem
- Determinar outcome terminal baseado em contexto
- Gerar resposta apropriada ao cliente
- Garantir que toda sessão termine com outcome válido

Conforme Funcionamento.md § 3.1 — outcomes canônicos:
HANDOFF_HUMAN, SELF_SERVE_INFO, ROUTE_EXTERNAL, SCHEDULED_FOLLOWUP,
AWAITING_USER, DUPLICATE_OR_SPAM, UNSUPPORTED, FAILED_INTERNAL
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pyloto_corp.domain.enums import Intent, Outcome
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.adapters.whatsapp.models import NormalizedWhatsAppMessage
    from pyloto_corp.application.session import SessionState

logger: logging.Logger = get_logger(__name__)


@dataclass(slots=True)
class AIResponse:
    """Resposta estruturada do orquestrador de IA.

    Contém:
    - Texto de resposta ao cliente (pode ser None)
    - Intenção detectada
    - Outcome terminal
    """

    reply_text: str | None = None
    outcome: Outcome | None = None
    intent: Intent | None = None
    confidence: float = 0.5


class IntentClassifier:
    """Classificação determinística de intenção de entrada."""

    def __init__(self) -> None:
        # Mapeamento de palavras-chave para intenções
        self._keywords: dict[Intent, list[str]] = {
            Intent.CUSTOM_SOFTWARE: [
                "sistema",
                "software",
                "customizado",
                "desenvolvimento",
                "app",
                "plataforma",
            ],
            Intent.SAAS_COMMUNICATION: [
                "whatsapp",
                "automação",
                "mensagens",
                "comunicação",
                "atendimento",
                "pyloto",
            ],
            Intent.PYLOTO_ENTREGA_REQUEST: [
                "entrega",
                "urgente",
                "agora",
                "pedir entrega",
            ],
            Intent.PYLOTO_ENTREGA_DRIVER_SIGNUP: [
                "entregador",
                "motorista",
                "cadastro",
                "trabalhar",
            ],
            Intent.INSTITUTIONAL: [
                "empresa",
                "sobre",
                "informação",
                "contato",
                "historia",
            ],
        }

    def classify(self, text: str) -> tuple[Intent, float]:
        """Classifica intenção com base em palavras-chave.

        Retorna (Intent, confidence 0.0-1.0).
        Se nenhuma palavr-chave bate, retorna ENTRY_UNKNOWN com confiança baixa.
        """
        text_lower = text.lower().strip()

        if not text_lower:
            return Intent.ENTRY_UNKNOWN, 0.0

        max_matches = 0
        matched_intent = Intent.ENTRY_UNKNOWN
        matched_confidence = 0.3

        for intent, keywords in self._keywords.items():
            matches = sum(1 for kw in keywords if kw in text_lower)
            if matches > max_matches:
                max_matches = matches
                matched_intent = intent
                # Confiança baseada em quantidade de matches
                matched_confidence = min(0.3 + (matches * 0.15), 0.95)

        return matched_intent, matched_confidence


class OutcomeDecider:
    """Lógica de decisão de outcome terminal baseada em contexto."""

    def decide(
        self,
        intent: Intent,
        session: SessionState | None = None,
        is_duplicate: bool = False,
    ) -> Outcome:
        """Decide outcome baseado em contexto.

        Regras simples (extendíveis):
        - Se duplicado: DUPLICATE_OR_SPAM
        - Se intent indeciso: SELF_SERVE_INFO
        - Se intent comercial: HANDOFF_HUMAN
        - Default: AWAITING_USER
        """

        if is_duplicate:
            return Outcome.DUPLICATE_OR_SPAM

        if intent == Intent.ENTRY_UNKNOWN:
            return Outcome.AWAITING_USER

        if intent == Intent.UNSUPPORTED:
            return Outcome.UNSUPPORTED

        # Intenções comerciais → handoff
        commercial_intents = {
            Intent.CUSTOM_SOFTWARE,
            Intent.SAAS_COMMUNICATION,
            Intent.PYLOTO_ENTREGA_DRIVER_SIGNUP,
            Intent.PYLOTO_ENTREGA_MERCHANT_SIGNUP,
        }

        if intent in commercial_intents:
            return Outcome.HANDOFF_HUMAN

        # Intenções informativas
        if intent == Intent.INSTITUTIONAL:
            return Outcome.SELF_SERVE_INFO

        # Entrega imediata → rota externa
        if intent == Intent.PYLOTO_ENTREGA_REQUEST:
            return Outcome.ROUTE_EXTERNAL

        return Outcome.AWAITING_USER


class AIOrchestrator:
    """Orquestra decisões de intenção e outcome."""

    def __init__(self) -> None:
        self._classifier = IntentClassifier()
        self._decider = OutcomeDecider()

    def process_message(
        self,
        message: NormalizedWhatsAppMessage,
        session: SessionState | None = None,
        is_duplicate: bool = False,
    ) -> AIResponse:
        """Processa mensagem normalizada e decide próximo passo.

        Args:
            message: Mensagem normalizada do WhatsApp
            session: Contexto de sessão (opcional)
            is_duplicate: Se mensagem é detectada como duplicada

        Returns:
            AIResponse com reply, outcome e intent
        """

        try:
            # Extrair texto para classificação
            text_input = message.text or ""

            # Classificar intenção
            intent, confidence = self._classifier.classify(text_input)

            # Decidir outcome
            outcome = self._decider.decide(intent, session=session, is_duplicate=is_duplicate)

            # Gerar resposta apropriada
            reply = self._generate_reply(intent, outcome)

            logger.info(
                "Message processed by orchestrator",
                extra={
                    "message_id": message.message_id[:8] + "...",
                    "intent": intent,
                    "confidence": round(confidence, 2),
                    "outcome": outcome,
                },
            )

            return AIResponse(
                reply_text=reply, outcome=outcome, intent=intent, confidence=confidence
            )
        except Exception as e:
            logger.error(
                "Orchestrator error",
                extra={
                    "message_id": getattr(message, "message_id", "unknown")[:8] + "...",
                    "error": str(e),
                },
            )
            return AIResponse(outcome=Outcome.FAILED_INTERNAL)

    def _generate_reply(self, intent: Intent, outcome: Outcome) -> str | None:
        """Gera texto de resposta baseado em intenção e outcome.

        Retorna None se não deve responder.
        """

        if outcome == Outcome.DUPLICATE_OR_SPAM:
            return None

        if outcome == Outcome.FAILED_INTERNAL:
            return None

        if outcome == Outcome.AWAITING_USER:
            return (
                "Olá! Bem-vindo à Pyloto. "
                "Qual é sua intenção? "
                "(Software customizado, SaaS, Entrega, ou outra?)"
            )

        if outcome == Outcome.HANDOFF_HUMAN:
            return "Perfeito! Vou conectá-lo com nosso time especializado. Um momento, por favor..."

        if outcome == Outcome.ROUTE_EXTERNAL:
            return (
                "Entendi que você quer uma entrega agora. "
                "Vou redirecionar você para nosso serviço de entrega..."
            )

        if outcome == Outcome.SELF_SERVE_INFO:
            return "Claro! Para mais informações, visite nosso site ou me faça mais perguntas."

        if outcome == Outcome.UNSUPPORTED:
            return "Desculpe, não consigo ajudar com isso no momento. Você tem outra dúvida?"

        return None
