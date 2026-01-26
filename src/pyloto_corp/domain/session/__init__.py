"""FSM Session — Estados, eventos e transições.

Exporta:
- SessionState: 10 estados canônicos
- SessionEvent: 14 eventos
- validate_transition: validador puro
- FSMEngine: dispatcher puro
"""

from pyloto_corp.domain.session.events import SessionEvent
from pyloto_corp.domain.session.states import (
    NON_TERMINAL_STATES,
    TERMINAL_STATES,
    SessionState,
)
from pyloto_corp.domain.session.transitions import validate_transition

__all__ = [
    "SessionState",
    "SessionEvent",
    "validate_transition",
    "TERMINAL_STATES",
    "NON_TERMINAL_STATES",
]
