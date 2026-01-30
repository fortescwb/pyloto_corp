"""Tabela de transições do FSM.

Conforme FSM_LLM_ARCHITECTURE_PYLOTO_CORP.md:
- TRANSITIONS[(current_state, event)] = next_state
- Estados terminais não aparecem como origem (no transitions out)
- Validação pura: sem side effects
"""

from __future__ import annotations

from pyloto_corp.domain.session.events import SessionEvent
from pyloto_corp.domain.session.states import TERMINAL_STATES, SessionState

# Tabela de transições: (current_state, event) → next_state
TRANSITIONS: dict[tuple[SessionState, SessionEvent], SessionState] = {
    # === INITIAL → ... ===
    (SessionState.INITIAL, SessionEvent.USER_SENT_TEXT): SessionState.TRIAGE,
    (SessionState.INITIAL, SessionEvent.USER_SENT_MEDIA): SessionState.TRIAGE,
    (SessionState.INITIAL, SessionEvent.SESSION_TIMEOUT): SessionState.TIMEOUT,
    (SessionState.INITIAL, SessionEvent.INTERNAL_ERROR): SessionState.ERROR,
    # === TRIAGE → ... ===
    (SessionState.TRIAGE, SessionEvent.EVENT_DETECTED): SessionState.COLLECTING_INFO,
    (SessionState.TRIAGE, SessionEvent.INTERNAL_ERROR): SessionState.ERROR,
    (SessionState.TRIAGE, SessionEvent.SESSION_TIMEOUT): SessionState.TIMEOUT,
    # === COLLECTING_INFO → ... ===
    (
        SessionState.COLLECTING_INFO,
        SessionEvent.USER_SENT_TEXT,
    ): SessionState.COLLECTING_INFO,
    (
        SessionState.COLLECTING_INFO,
        SessionEvent.USER_SELECTED_BUTTON,
    ): SessionState.COLLECTING_INFO,
    (
        SessionState.COLLECTING_INFO,
        SessionEvent.USER_SELECTED_LIST_ITEM,
    ): SessionState.COLLECTING_INFO,
    (
        SessionState.COLLECTING_INFO,
        SessionEvent.RESPONSE_GENERATED,
    ): SessionState.GENERATING_RESPONSE,
    (
        SessionState.COLLECTING_INFO,
        SessionEvent.HUMAN_HANDOFF_READY,
    ): SessionState.HANDOFF_HUMAN,
    (
        SessionState.COLLECTING_INFO,
        SessionEvent.SELF_SERVE_COMPLETE,
    ): SessionState.SELF_SERVE_INFO,
    (
        SessionState.COLLECTING_INFO,
        SessionEvent.EXTERNAL_ROUTE_READY,
    ): SessionState.ROUTE_EXTERNAL,
    (SessionState.COLLECTING_INFO, SessionEvent.SESSION_TIMEOUT): SessionState.TIMEOUT,
    (SessionState.COLLECTING_INFO, SessionEvent.INTERNAL_ERROR): SessionState.ERROR,
    # === GENERATING_RESPONSE → ... ===
    (
        SessionState.GENERATING_RESPONSE,
        SessionEvent.MESSAGE_TYPE_SELECTED,
    ): SessionState.HANDOFF_HUMAN,
    (
        SessionState.GENERATING_RESPONSE,
        SessionEvent.SELF_SERVE_COMPLETE,
    ): SessionState.SELF_SERVE_INFO,
    (
        SessionState.GENERATING_RESPONSE,
        SessionEvent.EXTERNAL_ROUTE_READY,
    ): SessionState.ROUTE_EXTERNAL,
    (SessionState.GENERATING_RESPONSE, SessionEvent.SESSION_TIMEOUT): SessionState.TIMEOUT,
    (SessionState.GENERATING_RESPONSE, SessionEvent.INTERNAL_ERROR): SessionState.ERROR,
    # === Estados Terminais: SEM transições de saída ===
    # HANDOFF_HUMAN, SELF_SERVE_INFO, ROUTE_EXTERNAL, SCHEDULED_FOLLOWUP, TIMEOUT, ERROR
    # Nenhuma transição saindo desses estados (FSM finito)
}


def validate_transition(
    current_state: SessionState, event: SessionEvent
) -> tuple[bool, SessionState | None, str]:
    """Valida se uma transição é permitida.

    Retorna:
    - (True, next_state, ""): transição válida
    - (False, None, motivo): transição inválida

    Nunca lança exceção; apenas valida.
    """
    key = (current_state, event)

    if current_state in TERMINAL_STATES:
        return (
            False,
            None,
            f"Terminal state {current_state} has no transitions",
        )

    if key not in TRANSITIONS:
        return (
            False,
            None,
            f"No transition from {current_state} on event {event}",
        )

    next_state = TRANSITIONS[key]
    return True, next_state, ""
