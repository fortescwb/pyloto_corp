from __future__ import annotations

from pyloto_corp.application.master_decider import decide_master
from pyloto_corp.domain.conversation_state import (
    ConversationState,
    StateSelectorOutput,
    StateSelectorStatus,
)
from pyloto_corp.domain.master_decision import MasterDecisionInput
from pyloto_corp.domain.response_generator import ResponseGeneratorOutput


class FailingLLM:
    def complete(self, prompt, model=None, timeout=None):
        raise RuntimeError("boom")


def _state_decision():
    return StateSelectorOutput(
        selected_state=ConversationState.HANDOFF_HUMAN,
        confidence=0.8,
        accepted=True,
        next_state=ConversationState.HANDOFF_HUMAN,
        response_hint=None,
        status=StateSelectorStatus.DONE,
    )


def test_master_decider_fallback_safe():
    data = MasterDecisionInput(
        last_user_message="test",
        day_history=[],
        state_decision=_state_decision(),
        response_options=ResponseGeneratorOutput(
            responses=["r1", "r2", "r3"],
            response_style_tags=[],
            chosen_index=1,
            safety_notes=[],
        ),
        current_state=ConversationState.AWAITING_USER,
        correlation_id="c2",
    )

    out = decide_master(
        data,
        FailingLLM(),
        correlation_id="c2",
        model=None,
        timeout_seconds=1.0,
        confidence_threshold=0.7,
    )

    assert out.final_state == ConversationState.HANDOFF_HUMAN
    assert out.selected_response_text in data.response_options.responses
    assert out.message_type.value == "text"
    assert out.overall_confidence <= 0.8
