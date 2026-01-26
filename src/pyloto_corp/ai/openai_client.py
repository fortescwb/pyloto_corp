"""Cliente OpenAI para integração com ChatGPT.

Fornece abstração sobre a API OpenAI, com suporte a:
- Detecção de eventos (event detection)
- Geração de respostas (response generation)
- Seleção de tipo de mensagem (message type selection)

Todos os métodos incluem retry logic, timeout e fallback determinístico.
"""

from __future__ import annotations

import logging
from typing import Any

from openai import APIError, APITimeoutError, AsyncOpenAI

from pyloto_corp.ai import openai_parser, openai_prompts
from pyloto_corp.ai.contracts.event_detection import EventDetectionResult
from pyloto_corp.ai.contracts.message_type_selection import MessageTypeSelectionResult
from pyloto_corp.ai.contracts.response_generation import ResponseGenerationResult

from pyloto_corp.domain.enums import Intent
from pyloto_corp.observability.logging import get_logger

logger: logging.Logger = get_logger(__name__)


class OpenAIClientManager:
    """Gerenciador do cliente OpenAI com retry e timeout.

    Responsabilidades:
    - Inicializar cliente OpenAI com configurações corretas
    - Gerenciar retry e timeout para cada endpoint
    - Fornecer métodos para cada ponto de LLM (event, response, message_type)
    - Manter fallback determinístico em caso de erro
    """

    def __init__(self, api_key: str | None = None) -> None:
        """Inicializa cliente OpenAI."""
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = "gpt-4o-mini"
        self._timeout = 10.0
        self._max_retries = 2

    async def detect_event(
        self,
        user_input: str,
        session_history: list[dict[str, Any]] | None = None,
        known_intent: Intent | None = None,
    ) -> EventDetectionResult:
        """Detecta evento e intenção usando ChatGPT."""
        system_prompt = openai_prompts.get_event_detection_prompt()
        user_message = openai_prompts.format_event_detection_input(
            user_input, session_history, known_intent
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=150,
                timeout=self._timeout,
            )
            result_text = response.choices[0].message.content or ""
            return openai_parser.parse_event_detection_response(result_text)

        except (APIError, APITimeoutError) as e:
            logger.warning(
                "event_detection_error",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            return openai_parser._fallback_event_detection()

    async def generate_response(
        self,
        user_input: str,
        detected_intent: Intent,
        current_state: str,
        next_state: str,
        session_context: dict[str, Any] | None = None,
    ) -> ResponseGenerationResult:
        """Gera resposta usando ChatGPT."""
        system_prompt = openai_prompts.get_response_generation_prompt()
        user_message = openai_prompts.format_response_generation_input(
            user_input, detected_intent, current_state, next_state, session_context
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.4,
                max_tokens=400,
                timeout=self._timeout,
            )
            result_text = response.choices[0].message.content or ""
            return openai_parser.parse_response_generation_response(result_text)

        except (APIError, APITimeoutError) as e:
            logger.warning(
                "response_generation_error",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            return openai_parser._fallback_response_generation()

    async def select_message_type(
        self,
        text_content: str,
        options: list[dict[str, str]] | None = None,
        intent_type: str | None = None,
    ) -> MessageTypeSelectionResult:
        """Seleciona tipo de mensagem optimal usando ChatGPT."""
        system_prompt = openai_prompts.get_message_type_selection_prompt()
        user_message = openai_prompts.format_message_type_selection_input(
            text_content, options, intent_type
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.2,
                max_tokens=200,
                timeout=self._timeout,
            )
            result_text = response.choices[0].message.content or ""
            return openai_parser.parse_message_type_response(result_text)

        except (APIError, APITimeoutError) as e:
            logger.warning(
                "message_type_selection_error",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            return openai_parser._fallback_message_type_selection()


# Instância global (lazy init)
_openai_client: OpenAIClientManager | None = None


def get_openai_client(api_key: str | None = None) -> OpenAIClientManager:
    """Retorna instância global do cliente OpenAI."""
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAIClientManager(api_key=api_key)
    return _openai_client
