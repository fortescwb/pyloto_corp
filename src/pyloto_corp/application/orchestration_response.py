"""Orquestração de geração de respostas (Response Generator LLM).

Responsabilidade única: chamar response generator LLM e retornar opções.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyloto_corp.application.response_generator import generate_response_options
from pyloto_corp.domain.conversation_state import ConversationState
from pyloto_corp.domain.response_generator import ResponseGeneratorInput

if TYPE_CHECKING:
    from pyloto_corp.domain.conversation_state import StateSelectorOutput
    from pyloto_corp.domain.response_generator import ResponseGeneratorOutput


def orchestrate_response_generation(
    session: Any,
    message: Any,
    state_decision: StateSelectorOutput,
    response_generator_client: Any,
    response_generator_model: str | None,
    response_generator_timeout: int,
    response_generator_min_responses: int,
) -> ResponseGeneratorOutput | None:
    """Orquestra geração de respostas via response generator LLM.

    Retorna ResponseGeneratorOutput ou None se desabilitado/sem state_decision.
    """
    # Normalizar estado inválido para fallback seguro
    try:
        current_conv = ConversationState(session.current_state)
    except Exception:
        current_conv = ConversationState.AWAITING_USER

    rg_input = ResponseGeneratorInput(
        last_user_message=message.text or "",
        day_history=session.message_history,
        state_decision=state_decision,
        current_state=current_conv,
        candidate_next_state=state_decision.selected_state,
        confidence=state_decision.confidence,
        response_hint=state_decision.response_hint,
    )

    response_options = generate_response_options(
        rg_input,
        response_generator_client,
        correlation_id=message.message_id,
        model=response_generator_model,
        timeout_seconds=response_generator_timeout,
        min_responses=response_generator_min_responses,
    )

    return response_options
