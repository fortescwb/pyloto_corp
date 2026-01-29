from __future__ import annotations

from pyloto_corp.application.response_generator import generate_response_options
from pyloto_corp.domain.conversation_state import (
    ConversationState,
    StateSelectorOutput,
    StateSelectorStatus,
)
from pyloto_corp.domain.response_generator import ResponseGeneratorInput


class FakeStateDecision(StateSelectorOutput):
    pass


class EchoLLM:
    def complete(self, prompt, model=None, timeout=None):
        return {
            "responses": ["r1", "r2", "r3"],
            "response_style_tags": ["curta"],
            "chosen_index": 0,
            "safety_notes": ["ok"],
        }


class BrokenLLM:
    def complete(self, prompt, model=None, timeout=None):
        raise RuntimeError("fail")


def _state_decision(accepted: bool, confidence: float, hint: str | None = None):
    return StateSelectorOutput(
        selected_state=ConversationState.AWAITING_USER,
        confidence=confidence,
        accepted=accepted,
        next_state=ConversationState.AWAITING_USER,
        response_hint=hint or "Confirme, por favor.",
        status=StateSelectorStatus.IN_PROGRESS,
    )


def test_response_generator_uses_hint_on_low_confidence():
    data = ResponseGeneratorInput(
        last_user_message="ok valeu",
        day_history=[],
        state_decision=_state_decision(False, 0.4, "Confirme se encerramos"),
        current_state=ConversationState.AWAITING_USER,
        candidate_next_state=ConversationState.HANDOFF_HUMAN,
        confidence=0.4,
        response_hint="Confirme se encerramos",
    )
    out = generate_response_options(
        data,
        BrokenLLM(),
        correlation_id="c1",
        model=None,
        timeout_seconds=2.0,
        min_responses=3,
    )

    assert len(out.responses) >= 3
    assert any("Confirme" in r for r in out.responses)


def test_response_generator_returns_three_min():
    data = ResponseGeneratorInput(
        last_user_message="oi",
        day_history=[],
        state_decision=_state_decision(True, 0.9),
        current_state=ConversationState.AWAITING_USER,
        candidate_next_state=ConversationState.HANDOFF_HUMAN,
        confidence=0.9,
        response_hint=None,
    )
    out = generate_response_options(
        data,
        EchoLLM(),
        correlation_id="c2",
        model=None,
        timeout_seconds=2.0,
        min_responses=3,
    )

    assert len(out.responses) >= 3
    assert out.chosen_index == 0
