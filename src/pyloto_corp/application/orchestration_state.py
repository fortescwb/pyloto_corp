"""Orquestração de seleção de estado (State Selector LLM).

Responsabilidade única: chamar state selector LLM e retornar decisão.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyloto_corp.application.state_selector import select_next_state
from pyloto_corp.domain.conversation_state import (
    ConversationState,
    StateSelectorInput,
)

if TYPE_CHECKING:
    from pyloto_corp.domain.conversation_state import StateSelectorOutput


def orchestrate_state_selection(
    session: Any,
    message: Any,
    state_selector_client: Any,
    state_selector_model: str | None,
    state_selector_threshold: float,
) -> StateSelectorOutput | None:
    """Orquestra decisão de próximo estado via state selector LLM.

    Retorna StateSelectorOutput ou None se desabilitado.
    """
    try:
        current_conv = ConversationState(session.current_state)
    except Exception:
        current_conv = ConversationState("AWAITING_USER")

    possible_next = [
        ConversationState.AWAITING_USER,
        ConversationState.HANDOFF_HUMAN,
        ConversationState.SELF_SERVE_INFO,
        ConversationState.ROUTE_EXTERNAL,
        ConversationState.SCHEDULED_FOLLOWUP,
    ]

    selector_input = StateSelectorInput(
        current_state=current_conv,
        possible_next_states=possible_next,
        message_text=message.text or "",
        history_summary=[h.get("summary", "") for h in session.message_history],
    )

    state_decision = select_next_state(
        selector_input,
        state_selector_client,
        correlation_id=message.message_id,
        model=state_selector_model,
        confidence_threshold=state_selector_threshold,
    )

    if state_decision.accepted:
        session.current_state = state_decision.next_state.value
    else:
        session.message_history.append(
            {"summary": "state_hint", "hint": state_decision.response_hint}
        )

    return state_decision
