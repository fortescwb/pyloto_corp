from __future__ import annotations

from pyloto_corp.application.state_selector import select_next_state
from pyloto_corp.domain.conversation_state import (
    ConversationState,
    StateSelectorInput,
    StateSelectorStatus,
)


class EchoLLM:
    def __init__(self, base_confidence: float):
        self.base_confidence = base_confidence

    def complete(self, prompt, model=None):
        return {
            "selected_state": "HANDOFF_HUMAN",
            "confidence": self.base_confidence,
            "status": "in_progress",
        }


def test_precheck_clamps_confidence_on_closing():
    data = StateSelectorInput(
        current_state=ConversationState.AWAITING_USER,
        possible_next_states=[ConversationState.HANDOFF_HUMAN],
        message_text="ok, obrigado",
        open_items=["pendente"],
    )
    llm = EchoLLM(0.95)

    result = select_next_state(data, llm, correlation_id="c5")

    assert result.confidence < 0.7
    assert result.accepted is False
    assert result.status == StateSelectorStatus.NEEDS_CLARIFICATION
    assert result.response_hint


def test_precheck_detects_new_request():
    data = StateSelectorInput(
        current_state=ConversationState.AWAITING_USER,
        possible_next_states=[ConversationState.HANDOFF_HUMAN],
        message_text="agora quero outra coisa",
    )
    llm = EchoLLM(0.95)

    result = select_next_state(data, llm, correlation_id="c6")

    assert result.status == StateSelectorStatus.NEW_REQUEST_DETECTED
    assert result.accepted is False
    assert result.response_hint
