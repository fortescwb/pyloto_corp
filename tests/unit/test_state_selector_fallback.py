from __future__ import annotations

from pyloto_corp.application.state_selector import select_next_state
from pyloto_corp.domain.conversation_state import (
    ConversationState,
    StateSelectorInput,
)


class BrokenLLM:
    def complete(self, prompt, model=None):
        raise RuntimeError("boom")


def test_llm_failure_returns_safe_fallback():
    data = StateSelectorInput(
        current_state=ConversationState.AWAITING_USER,
        possible_next_states=[ConversationState.HANDOFF_HUMAN],
        message_text="teste",
    )
    llm = BrokenLLM()

    result = select_next_state(data, llm, correlation_id="c4")

    assert result.accepted is False
    assert result.confidence == 0.0
    assert result.next_state == ConversationState.AWAITING_USER
    assert result.response_hint
