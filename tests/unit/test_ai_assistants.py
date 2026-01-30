from __future__ import annotations

import pytest

from pyloto_corp.ai.assistant_event_detector import EventDetector
from pyloto_corp.ai.assistant_message_type import (
    MessageSafety,
    _build_message_plan_from_llm_result,
    _fallback_message_plan,
    build_message_type_input,
    choose_message_plan,
)
from pyloto_corp.ai.assistant_response_generator import ResponseGenerator
from pyloto_corp.ai.contracts.event_detection import EventDetectionRequest
from pyloto_corp.ai.contracts.response_generation import (
    ResponseGenerationRequest,
    ResponseGenerationResult,
    ResponseOption,
)
from pyloto_corp.ai.openai_parser import MessageTypeSelectionResult
from pyloto_corp.domain.enums import Intent
from pyloto_corp.domain.session.events import SessionEvent
from pyloto_corp.domain.session.states import SessionState


class DummyOpenAIClient:
    async def select_message_type(self, text_content, options, intent_type):
        return MessageTypeSelectionResult.model_construct(
            message_type="REACTION",
            parameters={"emoji": "wave"},
            confidence=0.9,
            rationale="wave",
            fallback=False,
        )


@pytest.mark.asyncio
async def test_event_detector_detects_keyword():
    detector = EventDetector()
    req = EventDetectionRequest(user_input="Preciso de um sistema completo")

    res = await detector.detect(req)

    assert res.detected_intent == Intent.CUSTOM_SOFTWARE
    assert res.event == SessionEvent.USER_SENT_TEXT
    assert res.confidence >= 0.5


@pytest.mark.asyncio
async def test_event_detector_returns_fallback_on_error(monkeypatch):
    detector = EventDetector()

    def boom(_request):
        raise RuntimeError("boom")

    monkeypatch.setattr(detector, "_detect_deterministic", boom)

    res = await detector.detect(EventDetectionRequest(user_input="algum input"))

    assert res.detected_intent == Intent.ENTRY_UNKNOWN
    assert res.requires_followup is True
    assert res.confidence == 0.5


@pytest.mark.asyncio
async def test_response_generator_builds_options_for_institutional():
    generator = ResponseGenerator()
    req = ResponseGenerationRequest(
        event=SessionEvent.USER_SENT_TEXT,
        detected_intent=Intent.INSTITUTIONAL,
        current_state=SessionState.INITIAL,
        next_state=SessionState.COLLECTING_INFO,
        user_input="Quero conhecer a Pyloto",
        confidence_event=0.9,
    )

    res = await generator.generate(req)

    assert res.options
    assert res.text_content
    assert res.confidence >= 0.6


@pytest.mark.asyncio
async def test_response_generator_fallback_on_exception(monkeypatch):
    generator = ResponseGenerator()

    def fail(_request):
        raise RuntimeError("failure")

    monkeypatch.setattr(generator, "_generate_deterministic", fail)

    req = ResponseGenerationRequest(
        event=SessionEvent.USER_SENT_TEXT,
        detected_intent=Intent.ENTRY_UNKNOWN,
        current_state=SessionState.INITIAL,
        next_state=SessionState.GENERATING_RESPONSE,
        user_input="ping",
        confidence_event=0.1,
    )

    res = await generator.generate(req)

    assert res.requires_human_review is True
    assert res.confidence == 0.3


def test_build_message_type_input_uses_defaults():
    generated = ResponseGenerationResult(
        text_content="resposta",
        options=[ResponseOption(id="1", title="Opcao 1")],
        requires_human_review=False,
        confidence=0.7,
    )

    context = build_message_type_input(
        state=SessionState.GENERATING_RESPONSE.value,
        event=SessionEvent.USER_SENT_TEXT.value,
        generated_response=generated,
        channel_caps=None,
    )

    assert context["options_count"] == 1
    assert "buttons" in context["channel_capabilities"]


@pytest.mark.asyncio
async def test_choose_message_plan_builds_reaction_plan():
    generated = ResponseGenerationResult(
        text_content="Olá",
        options=[],
        requires_human_review=False,
        confidence=0.9,
    )

    plan = await choose_message_plan(
        DummyOpenAIClient(),
        state=SessionState.GENERATING_RESPONSE.value,
        event=SessionEvent.USER_SENT_TEXT.value,
        generated_response=generated,
    )

    assert plan.kind == "REACTION"
    assert plan.reaction == "wave"
    assert isinstance(plan.safety, MessageSafety)


def test_build_message_plan_from_llm_result_with_list():
    generated = ResponseGenerationResult(
        text_content="Escolha uma opção",
        options=[ResponseOption(id="opt1", title="Primeira")],
        requires_human_review=False,
        confidence=0.8,
    )
    safety = MessageSafety(pii_risk="low")
    llm_result = MessageTypeSelectionResult.model_construct(
        message_type="INTERACTIVE_LIST",
        parameters={},
        confidence=0.85,
        rationale="lista",
        fallback=False,
    )

    plan = _build_message_plan_from_llm_result(llm_result, generated, safety)

    assert plan.kind == "INTERACTIVE_LIST"
    assert plan.interactive == generated.options
    assert plan.safety is safety


def test_fallback_message_plan_when_llm_result_invalid():
    generated = ResponseGenerationResult(
        text_content="Texto simples",
        options=[ResponseOption(id="a", title="Apenas um")],
        requires_human_review=True,
        confidence=0.4,
    )
    safety = MessageSafety(pii_risk="medium", require_handoff=True)

    plan = _fallback_message_plan(generated, safety)

    assert plan.safety.require_handoff is True
    assert plan.kind in {"INTERACTIVE_BUTTON", "TEXT"}
