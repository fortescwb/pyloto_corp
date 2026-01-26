"""LLM #2 — Geração de resposta.

Responsabilidade:
- Gerar resposta contextualizada baseada em evento + estado
- Sugerir opções (se aplicável)
- Retornar ResponseGenerationResult
"""

from __future__ import annotations

import logging

from pyloto_corp.ai.contracts.response_generation import (
    ResponseGenerationRequest,
    ResponseGenerationResult,
    ResponseOption,
)
from pyloto_corp.domain.enums import Intent
from pyloto_corp.domain.session.states import SessionState
from pyloto_corp.observability.logging import get_logger

logger: logging.Logger = get_logger(__name__)


class ResponseGenerator:
    """Gerador de respostas — conteúdo contextualizado."""

    def __init__(self) -> None:
        pass

    async def generate(
        self, request: ResponseGenerationRequest
    ) -> ResponseGenerationResult:
        """Gera resposta a partir do evento + estado + contexto.

        Args:
            request: ResponseGenerationRequest

        Returns:
            ResponseGenerationResult com texto + opções

        Contrato:
        - Nunca lança exceção
        - Text_content sempre válido (1-4096 chars)
        - Opções validadas conforme count
        - Confidence entre 0.0 e 1.0
        """
        try:
            result = self._generate_deterministic(request)
            logger.debug(
                "Response generated",
                extra={
                    "intent": request.detected_intent,
                    "next_state": request.next_state,
                    "options_count": len(result.options),
                    "confidence": result.confidence,
                },
            )
            return result
        except Exception as e:
            logger.error(
                "Response generation failed",
                extra={"error_type": type(e).__name__},
            )
            # Fallback: resposta neutra
            return ResponseGenerationResult(
                text_content="Desculpe, não consegui processar sua solicitação. "
                "Poderia tentar novamente?",
                options=[],
                confidence=0.3,
                requires_human_review=True,
                rationale="Fallback: erro na geração",
            )

    def _generate_deterministic(
        self, request: ResponseGenerationRequest
    ) -> ResponseGenerationResult:
        """Implementação determinística com fallback.

        Sem LLM real: usa templates simples baseados em estado/intenção.
        """
        # Template simples por intenção
        text_by_intent: dict[Intent, str] = {
            Intent.CUSTOM_SOFTWARE: (
                "Excelente! Você procura um sistema customizado. "
                "Para qualificar melhor sua demanda, poderia informar: "
                "tipo de cliente, problema atual e prazo esperado?"
            ),
            Intent.SAAS_COMMUNICATION: (
                "Perfeito! O Pyloto oferece automação de comunicação. "
                "Qual é o principal canal de atendimento que você usa?"
            ),
            Intent.PYLOTO_ENTREGA_REQUEST: (
                "Para solicitações de entrega urgente, "
                "dirija-se ao canal específico de Pyloto Entrega. "
                "Um momento..."
            ),
            Intent.INSTITUTIONAL: (
                "A Pyloto oferece 3 vertentes principais: "
                "Sistemas Customizados, SaaS de Comunicação e Entrega. "
                "Qual delas te interessa?"
            ),
            Intent.ENTRY_UNKNOWN: (
                "Olá! Bem-vindo à Pyloto. "
                "Para melhor atendê-lo, poderia detalhar sua necessidade?"
            ),
        }

        # Obter texto base
        text = text_by_intent.get(
            request.detected_intent,
            text_by_intent[Intent.ENTRY_UNKNOWN],
        )

        # Sugerir opções baseadas no estado
        options: list[ResponseOption] = []
        if (
            request.next_state == SessionState.COLLECTING_INFO
            and request.detected_intent == Intent.INSTITUTIONAL
        ):
            options = [
                ResponseOption(
                    id="custom_software",
                    title="Sistemas Customizados",
                ),
                ResponseOption(
                    id="saas_communication",
                    title="SaaS Comunicação",
                ),
                ResponseOption(
                    id="pyloto_entrega",
                    title="Pyloto Entrega",
                ),
            ]

        return ResponseGenerationResult(
            text_content=text,
            options=options,
            suggested_next_state=request.next_state,
            requires_human_review=False,
            confidence=0.7 if options else 0.6,
            rationale="Generated from intent + state",
        )
