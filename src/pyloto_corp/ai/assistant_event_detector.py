"""LLM #1 — Detecção de evento.

Responsabilidade:
- Converter input do usuário em SessionEvent
- Classificar intenção
- Retornar EventDetectionResult
"""

from __future__ import annotations

import logging

from pyloto_corp.ai.contracts.event_detection import (
    EventDetectionRequest,
    EventDetectionResult,
)
from pyloto_corp.domain.enums import Intent
from pyloto_corp.domain.session.events import SessionEvent
from pyloto_corp.observability.logging import get_logger

logger: logging.Logger = get_logger(__name__)


class EventDetector:
    """Detector de eventos — classifica input do usuário."""

    def __init__(self) -> None:
        pass

    async def detect(self, request: EventDetectionRequest) -> EventDetectionResult:
        """Detecta evento e intenção a partir do input do usuário.

        Args:
            request: EventDetectionRequest com user_input + contexto

        Returns:
            EventDetectionResult com evento, intenção e confiança

        Contrato:
        - Nunca lança exceção; sempre retorna resultado válido
        - Fallback para USER_SENT_TEXT + ENTRY_UNKNOWN se ambiguo
        - Confidence sempre entre 0.0 e 1.0
        """
        try:
            # Aqui entraria chamada ao LLM real (GPT, Claude, etc)
            # Por agora, implementamos detector deterministico (fallback)
            result = self._detect_deterministic(request)
            logger.debug(
                "Event detected",
                extra={
                    "event": result.event,
                    "intent": result.detected_intent,
                    "confidence": result.confidence,
                },
            )
            return result
        except Exception as e:
            logger.error(
                "Event detection failed",
                extra={"error_type": type(e).__name__},
            )
            # Fallback seguro: texto com intenção desconhecida
            return EventDetectionResult(
                event=SessionEvent.USER_SENT_TEXT,
                detected_intent=Intent.ENTRY_UNKNOWN,
                confidence=0.5,
                requires_followup=True,
                rationale="Fallback: erro na detecção",
            )

    def _detect_deterministic(self, request: EventDetectionRequest) -> EventDetectionResult:
        """Implementação determinística com fallback.

        Sem side effects; apenas lógica pura.
        """
        text_lower = request.user_input.lower().strip()

        # Heurística simples (substituir por LLM real depois)
        if not text_lower:
            return EventDetectionResult(
                event=SessionEvent.USER_SENT_TEXT,
                detected_intent=Intent.ENTRY_UNKNOWN,
                confidence=0.3,
                requires_followup=True,
            )

        # Palavras-chave simplificadas
        keywords_to_intent: dict[str, Intent] = {
            "sistema": Intent.CUSTOM_SOFTWARE,
            "software": Intent.CUSTOM_SOFTWARE,
            "whatsapp": Intent.SAAS_COMMUNICATION,
            "automação": Intent.SAAS_COMMUNICATION,
            "entrega": Intent.PYLOTO_ENTREGA_REQUEST,
            "entregador": Intent.PYLOTO_ENTREGA_DRIVER_SIGNUP,
            "empresa": Intent.INSTITUTIONAL,
        }

        detected_intent = Intent.ENTRY_UNKNOWN
        max_matches = 0
        for keyword, intent in keywords_to_intent.items():
            matches = text_lower.count(keyword)
            if matches > max_matches:
                max_matches = matches
                detected_intent = intent

        # Confiança proporcional ao número de matches
        confidence = min(0.5 + (max_matches * 0.2), 1.0)

        return EventDetectionResult(
            event=SessionEvent.USER_SENT_TEXT,
            detected_intent=detected_intent,
            confidence=confidence,
            requires_followup=(confidence < 0.7),
            rationale=(f"Detected intent: {detected_intent}, matches: {max_matches}"),
        )
