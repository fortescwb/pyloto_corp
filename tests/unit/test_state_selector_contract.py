from __future__ import annotations

from pyloto_corp.application.state_selector import select_next_state
from pyloto_corp.domain.conversation_state import (
    ConversationState,
    StateSelectorInput,
)


class FakeLLM:
    def __init__(self, payload: dict):
        self.payload = payload

    def complete(self, prompt, model=None):
        return self.payload


def _build_input():
    return StateSelectorInput(
        current_state=ConversationState.AWAITING_USER,
        possible_next_states=[ConversationState.HANDOFF_HUMAN, ConversationState.SELF_SERVE_INFO],
        message_text="preciso falar com humano",
    )


def test_confidence_gate_accepts_transition():
    data = _build_input()
    llm = FakeLLM({"selected_state": "HANDOFF_HUMAN", "confidence": 0.9, "status": "done"})

    result = select_next_state(data, llm, correlation_id="c1")

    assert result.accepted is True
    assert result.next_state == ConversationState.HANDOFF_HUMAN


def test_confidence_gate_rejects_and_requires_hint():
    data = _build_input()
    llm = FakeLLM({"selected_state": "SELF_SERVE_INFO", "confidence": 0.5, "status": "in_progress"})

    result = select_next_state(data, llm, correlation_id="c2")

    assert result.accepted is False
    assert result.next_state == ConversationState.AWAITING_USER
    assert result.response_hint


def test_invalid_selected_state_falls_back():
    data = _build_input()
    llm = FakeLLM({"selected_state": "INVALID", "confidence": 0.9, "status": "done"})

    result = select_next_state(data, llm, correlation_id="c3")

    assert result.selected_state == ConversationState.AWAITING_USER
    assert result.next_state == ConversationState.AWAITING_USER
