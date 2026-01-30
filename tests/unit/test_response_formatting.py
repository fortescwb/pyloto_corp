from __future__ import annotations

from pyloto_corp.application.response_formatting import apply_otto_intro_if_first
from pyloto_corp.domain.constants.otto import OTTO_INTRO_TEXT


def test_apply_otto_intro_first_message():
    reply = apply_otto_intro_if_first("Olá, tudo bem?", True)

    assert reply is not None
    assert reply.startswith(OTTO_INTRO_TEXT)


def test_apply_otto_intro_skips_when_already_prefixed():
    text = f"{OTTO_INTRO_TEXT}\n\nOlá"

    assert apply_otto_intro_if_first(text, True) == text


def test_apply_otto_intro_returns_original_when_not_first_or_none():
    assert apply_otto_intro_if_first("oi", False) == "oi"
    assert apply_otto_intro_if_first(None, True) is None
