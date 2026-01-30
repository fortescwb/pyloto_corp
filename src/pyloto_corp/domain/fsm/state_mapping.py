"""Mapeamento explícito entre FSM interno e estado conversacional (LLM-facing).

Evita conversões implícitas espalhadas e garante fallback seguro.
"""

from __future__ import annotations

from typing import Any

from pyloto_corp.domain.conversation_state import ConversationState as LLMConversationState
from pyloto_corp.domain.fsm_states import ConversationState as FSMConversationState
from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)

# Mapeamento explícito FSM -> LLM-facing ConversationState
_FSM_TO_LLM_MAP: dict[FSMConversationState, LLMConversationState] = {
    FSMConversationState.INIT: LLMConversationState.INIT,
    FSMConversationState.IDENTIFYING: LLMConversationState.INIT,
    FSMConversationState.UNDERSTANDING_INTENT: LLMConversationState.INIT,
    FSMConversationState.PROCESSING: LLMConversationState.INIT,
    FSMConversationState.GENERATING_RESPONSE: LLMConversationState.INIT,
    FSMConversationState.SELECTING_MESSAGE_TYPE: LLMConversationState.INIT,
    FSMConversationState.AWAITING_USER: LLMConversationState.AWAITING_USER,
    FSMConversationState.ESCALATING: LLMConversationState.HANDOFF_HUMAN,
    FSMConversationState.COMPLETED: LLMConversationState.SELF_SERVE_INFO,
    FSMConversationState.FAILED: LLMConversationState.FAILED_INTERNAL,
    FSMConversationState.SPAM: LLMConversationState.DUPLICATE_OR_SPAM,
}


def map_fsm_to_conversation_state(
    fsm_state: Any,
) -> LLMConversationState:
    """Mapeia um estado da FSM para o estado conversacional exposto à LLM.

    Se o estado não for reconhecido, retorna `LLMConversationState.INIT` e emite
    um log de aviso estruturado sem PII.
    """
    try:
        mapped = _FSM_TO_LLM_MAP.get(fsm_state)
        if mapped is not None:
            return mapped
    except Exception:
        # continuar para fallback
        pass

    logger.warning(
        "fsm_state_mapping_fallback",
        extra={
            "event": "fsm_state_mapping_fallback",
            "unknown_state": str(fsm_state),
            "normalized_to": LLMConversationState.INIT.value,
        },
    )
    return LLMConversationState.INIT
