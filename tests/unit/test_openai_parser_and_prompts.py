from __future__ import annotations

from pyloto_corp.ai import openai_parser, openai_prompts
from pyloto_corp.domain.enums import Intent
from pyloto_corp.domain.session.events import SessionEvent


def test_parse_event_detection_response_and_fallback():
    raw = "\n".join(
        [
            "```json",
            "{"\
            '"event": "USER_SENT_TEXT", "detected_intent": "CUSTOM_SOFTWARE", '
            '"confidence": 0.9, "requires_followup": false' + "}",
            "```",
        ]
    )
    parsed = openai_parser.parse_event_detection_response(raw)

    assert parsed.event == SessionEvent.USER_SENT_TEXT
    assert parsed.detected_intent == "CUSTOM_SOFTWARE"

    fallback = openai_parser.parse_event_detection_response("not json")
    assert fallback.requires_followup is True


def test_parse_response_generation_response_truncates_long_text():
    long_text = "x" * 4100
    raw = (
        "{" + f'"text_content": "{long_text}", "options": [], "requires_human_review": false' + "}"
    )
    parsed = openai_parser.parse_response_generation_response(raw)

    assert parsed.text_content.startswith("x")
    assert len(parsed.text_content) <= 4096


def test_parse_message_type_response_and_fallback():
    raw = """{"message_type": "reaction", "parameters": {"emoji": ":)"}, "confidence": 0.7}"""
    parsed = openai_parser.parse_message_type_response(raw)

    assert parsed.message_type.value == "reaction"

    fallback = openai_parser.parse_message_type_response("")
    assert fallback.fallback is True


def test_prompts_and_formatters_return_expected_sections():
    event_prompt = openai_prompts.get_event_detection_prompt()
    assert "Instruções de Detecção" in event_prompt

    resp_prompt = openai_prompts.get_response_generation_prompt()
    assert "Instruções de Geração" in resp_prompt

    msg_prompt = openai_prompts.get_message_type_selection_prompt()
    assert "Tipos Disponíveis" in msg_prompt

    formatted_event = openai_prompts.format_event_detection_input(
        "texto", session_history=[{"msg": "a"}], known_intent=Intent.INSTITUTIONAL
    )
    assert "Intenção anterior" in formatted_event

    formatted_response = openai_prompts.format_response_generation_input(
        "pedido",
        Intent.CUSTOM_SOFTWARE,
        "INITIAL",
        "COLLECTING_INFO",
        {"lead": "dados"},
    )
    assert "Contexto da sessão" in formatted_response

    formatted_message_type = openai_prompts.format_message_type_selection_input(
        "texto",
        options=[{"title": "Opção 1"}, {"title": "Opção 2"}],
        intent_type="CUSTOM_SOFTWARE",
    )
    assert "Opções disponíveis" in formatted_message_type
