"""Fonte única do estado inicial da FSM.

Define o estado inicial canônico utilizado pelo pipeline e pelo state selector.
"""

from __future__ import annotations

from pyloto_corp.domain.conversation_state import ConversationState

# Estado inicial canônico da FSM (não depende de LLM nem de prompt)
INITIAL_STATE: ConversationState = ConversationState.INIT


def possible_next_states_for(state: ConversationState) -> list[ConversationState]:
    """Retorna os possíveis próximos estados para um dado estado atual.

    Converte explicitamente os estados da FSM interna para estados
    conversacionais (LLM-facing) usando `map_fsm_to_conversation_state`.
    """
    from pyloto_corp.domain.fsm.state_mapping import map_fsm_to_conversation_state
    from pyloto_corp.domain.fsm_states import FSMStateMachine

    fsm_next = FSMStateMachine.VALID_TRANSITIONS.get(state, set())
    mapped = [map_fsm_to_conversation_state(s) for s in fsm_next]
    # Deduplicação preservando ordem
    seen = set()
    result: list[ConversationState] = []
    for s in mapped:
        if s.value not in seen:
            result.append(s)
            seen.add(s.value)
    return result
