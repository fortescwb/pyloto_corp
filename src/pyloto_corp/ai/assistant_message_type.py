"""Modelos e orquestração para seleção de tipo de mensagem.

Responsabilidades:
- Definir contratos para planos de mensagem (MessagePlan, MessageSafety)
- Construir input contextualizado para LLM #3
- Orquestrar chamada ao LLM e aplicar fallbacks
"""

from __future__ import annotations

from dataclasses import dataclass

from pyloto_corp.ai.contracts.response_generation import ResponseGenerationResult
from pyloto_corp.ai.openai_client import OpenAIClientManager
from pyloto_corp.ai.sanitizer import sanitize_response_content
from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MessageSafety:
    """Nível de segurança e risco de PII."""

    pii_risk: str  # "low", "medium", "high"
    require_handoff: bool = False  # Se true, escalar para humano


@dataclass
class MessagePlan:
    """Plano de entrega de mensagem ao usuário.

    Define tipo, conteúdo e parâmetros da mensagem.
    """

    kind: str  # "TEXT", "INTERACTIVE_BUTTON", "REACTION", "STICKER", etc.
    reason: str  # Explicação breve da escolha
    text: str = ""  # Conteúdo de texto principal
    interactive: list[dict[str, str]] | None = None  # Botões/opções
    reaction: str | None = None  # Emoji para reação
    sticker: str | None = None  # ID ou URL do sticker
    safety: MessageSafety | None = None
    confidence: float = 0.7

    def __post_init__(self) -> None:
        """Validações pós-inicialização."""
        if self.safety is None:
            self.safety = MessageSafety(pii_risk="low", require_handoff=False)


def build_message_type_input(
    state: str,
    event: str,
    generated_response: ResponseGenerationResult,
    channel_caps: dict[str, bool] | None = None,
) -> dict[str, str]:
    """Constrói input contextualizado para LLM #3 (message type selection).

    Args:
        state: Estado FSM atual (ex: "GENERATING_RESPONSE")
        event: Evento detectado (ex: "USER_SENT_TEXT")
        generated_response: Resultado de LLM #2 (response generation)
        channel_caps: Capacidades do canal (ex: {"buttons": True, "stickers": False})

    Returns:
        Dict com contexto completo para decisão de tipo de mensagem
    """
    if channel_caps is None:
        channel_caps = {
            "buttons": True,
            "lists": True,
            "media": True,
            "reactions": False,
            "stickers": False,
        }

    # Sanitizar conteúdo antes de enviar para LLM #3 (defesa em profundidade)
    sanitized_text = sanitize_response_content(generated_response.text_content)

    context = {
        "state": state,
        "event": event,
        "text_content": sanitized_text,
        "options_count": len(generated_response.options or []),
        "requires_human_review": str(generated_response.requires_human_review),
        "channel_capabilities": str(channel_caps),
        "response_confidence": str(generated_response.confidence),
    }

    return context


async def choose_message_plan(
    openai_client: OpenAIClientManager,
    state: str,
    event: str,
    generated_response: ResponseGenerationResult,
) -> MessagePlan:
    """Orquestra seleção de tipo de mensagem via LLM #3.

    Ordem de execução (CRÍTICA):
    1. FSM (determine state)
    2. LLM #1 (detect event)
    3. LLM #2 (generate response) ← generated_response recebido como argumento
    4. LLM #3 (select message type) ← AQUI, DEPOIS de LLM #2

    Args:
        openai_client: Cliente OpenAI para chamar LLM #3
        state: Estado FSM atual
        event: Evento detectado
        generated_response: Resposta gerada (LLM #2)

    Returns:
        MessagePlan com decisão de tipo de mensagem
    """
    # Construir input contextualizado
    context_input = build_message_type_input(state, event, generated_response)

    # Chamar LLM #3 (select_message_type)
    message_type_result = await openai_client.select_message_type(
        text_content=generated_response.text_content,
        options=generated_response.options,
        intent_type=context_input.get("event", "UNKNOWN"),
    )

    # Validar se resposta requer handoff
    safety = MessageSafety(
        pii_risk="low" if message_type_result.confidence > 0.6 else "medium",
        require_handoff=generated_response.requires_human_review,
    )

    # Converter resultado LLM #3 para MessagePlan
    return _build_message_plan_from_llm_result(message_type_result, generated_response, safety)


def _build_message_plan_from_llm_result(
    llm_result: dict,
    generated_response: ResponseGenerationResult,
    safety: MessageSafety,
) -> MessagePlan:
    """Converte resultado LLM #3 para MessagePlan tipado.

    Args:
        llm_result: Resultado de select_message_type (parsed e validado)
        generated_response: Contexto da resposta gerada
        safety: Nível de segurança

    Returns:
        MessagePlan com todos os campos preenchidos
    """
    from pyloto_corp.ai.openai_parser import MessageTypeSelectionResult

    if not isinstance(llm_result, MessageTypeSelectionResult):
        return _fallback_message_plan(generated_response, safety)

    message_type = llm_result.message_type or "TEXT"
    parameters = llm_result.parameters or {}

    # Mapear tipo de mensagem para MessagePlan
    if message_type == "INTERACTIVE_BUTTON":
        return MessagePlan(
            kind="INTERACTIVE_BUTTON",
            reason=llm_result.rationale,
            text=generated_response.text_content,
            interactive=generated_response.options,
            safety=safety,
            confidence=llm_result.confidence,
        )

    elif message_type == "INTERACTIVE_LIST":
        return MessagePlan(
            kind="INTERACTIVE_LIST",
            reason=llm_result.rationale,
            text=generated_response.text_content,
            interactive=generated_response.options,
            safety=safety,
            confidence=llm_result.confidence,
        )

    elif message_type == "REACTION":
        emoji = parameters.get("emoji", "👍")
        return MessagePlan(
            kind="REACTION",
            reason=llm_result.rationale,
            reaction=emoji,
            safety=safety,
            confidence=llm_result.confidence,
        )

    elif message_type == "STICKER":
        sticker_id = parameters.get("sticker_id")
        return MessagePlan(
            kind="STICKER",
            reason=llm_result.rationale,
            sticker=sticker_id,
            safety=safety,
            confidence=llm_result.confidence,
        )

    else:
        # Padrão: texto simples
        return MessagePlan(
            kind="TEXT",
            reason=llm_result.rationale,
            text=generated_response.text_content,
            safety=safety,
            confidence=llm_result.confidence,
        )


def _fallback_message_plan(
    generated_response: ResponseGenerationResult,
    safety: MessageSafety,
) -> MessagePlan:
    """Fallback determinístico para message plan."""
    logger.warning(
        "message_plan_fallback",
        extra={"reason": "LLM #3 result parsing failed", "safety": str(safety)},
    )

    # Heurística simples: se tem opções, usar botões; senão, texto
    if generated_response.options and len(generated_response.options) <= 3:
        return MessagePlan(
            kind="INTERACTIVE_BUTTON",
            reason="Fallback heurística: 3 ou menos opções = botões",
            text=generated_response.text_content,
            interactive=generated_response.options,
            safety=safety,
            confidence=0.5,
        )

    return MessagePlan(
        kind="TEXT",
        reason="Fallback: texto simples (sem opções ou parse failed)",
        text=generated_response.text_content,
        safety=safety,
        confidence=0.4,
    )
