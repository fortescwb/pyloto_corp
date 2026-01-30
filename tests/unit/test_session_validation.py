from __future__ import annotations

from pyloto_corp.application.session_validation import check_session_validation
from pyloto_corp.domain.enums import Outcome


class DummyFlood:
    def __init__(self, flooded: bool = False) -> None:
        self._flooded = flooded

    def check_and_record(self, session_id: str):
        class Result:
            def __init__(self, is_flooded: bool) -> None:
                self.is_flooded = is_flooded

        return Result(self._flooded)


class DummySpam:
    def __init__(self, spam: bool = False) -> None:
        self._spam = spam

    def is_spam(self, _text: str) -> bool:  # pragma: no cover - trivial
        return self._spam


class DummyAbuse:
    def __init__(self, abuse: bool = False) -> None:
        self._abuse = abuse

    def is_abuse(self, _session) -> bool:  # pragma: no cover - trivial
        return self._abuse


class DummySession:
    def __init__(self, at_capacity: bool = False) -> None:
        self.session_id = "session-test"

        class Queue:
            def __init__(self, at_capacity: bool) -> None:
                self._at_capacity = at_capacity

            def is_at_capacity(self) -> bool:
                return self._at_capacity

        self.intent_queue = Queue(at_capacity)


class DummyMessage:
    def __init__(self, text: str) -> None:
        self.text = text


def test_validation_passes_when_clean():
    session = DummySession(at_capacity=False)
    is_valid, outcome = check_session_validation(
        DummyMessage("ok"), session, None, DummySpam(False), DummyAbuse(False)
    )

    assert is_valid is True
    assert outcome is None


def test_validation_blocks_on_flood():
    session = DummySession()
    is_valid, outcome = check_session_validation(
        DummyMessage("ok"), session, DummyFlood(True), DummySpam(False), DummyAbuse(False)
    )

    assert is_valid is False
    assert outcome == Outcome.DUPLICATE_OR_SPAM


def test_validation_blocks_on_spam():
    session = DummySession()
    is_valid, outcome = check_session_validation(
        DummyMessage("spam"), session, DummyFlood(False), DummySpam(True), DummyAbuse(False)
    )

    assert is_valid is False
    assert outcome == Outcome.DUPLICATE_OR_SPAM


def test_validation_blocks_on_abuse():
    session = DummySession()
    is_valid, outcome = check_session_validation(
        DummyMessage("ok"), session, DummyFlood(False), DummySpam(False), DummyAbuse(True)
    )

    assert is_valid is False
    assert outcome == Outcome.DUPLICATE_OR_SPAM


def test_validation_blocks_on_intent_capacity():
    session = DummySession(at_capacity=True)
    is_valid, outcome = check_session_validation(
        DummyMessage("ok"), session, DummyFlood(False), DummySpam(False), DummyAbuse(False)
    )

    assert is_valid is False
    assert outcome == Outcome.SCHEDULED_FOLLOWUP
