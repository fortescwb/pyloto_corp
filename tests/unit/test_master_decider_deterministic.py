from __future__ import annotations

from pyloto_corp.application.master_decider import decide_master
from pyloto_corp.domain.conversation_state import (
    ConversationState,
    StateSelectorOutput,
    StateSelectorStatus,
)
from pyloto_corp.domain.master_decision import MasterDecisionInput
from pyloto_corp.domain.response_generator import ResponseGeneratorOutput


class DummyLLM:
    def complete(self, prompt, model=None, timeout=None):
        return {}


def _state_decision(accepted: bool, confidence: float, hint: str | None = None):
    return StateSelectorOutput(
        selected_state=ConversationState.AWAITING_USER,
        confidence=confidence,
        accepted=accepted,
        next_state=ConversationState.AWAITING_USER,
        response_hint=hint,
        status=(
            StateSelectorStatus.NEEDS_CLARIFICATION
            if not accepted
            else StateSelectorStatus.DONE
        ),
    )


def test_deterministic_uses_hint_and_keeps_state():
    data = MasterDecisionInput(
        last_user_message="ok",
        day_history=[],
        state_decision=_state_decision(False, 0.5, "Confirme se encerramos"),
        response_options=ResponseGeneratorOutput(
            responses=["Confirme se encerramos?", "Outra", "Mais uma"],
            response_style_tags=[],
            chosen_index=0,
            safety_notes=[],
        ),
        current_state=ConversationState.AWAITING_USER,
        correlation_id="c1",
    )
    out = decide_master(
        data,
        DummyLLM(),
        correlation_id="c1",
        model=None,
        timeout_seconds=1.0,
        confidence_threshold=0.7,
    )

    assert out.apply_state is False
    assert out.final_state == ConversationState.AWAITING_USER
    assert "confirm" in out.reason or "hint" in out.reason
