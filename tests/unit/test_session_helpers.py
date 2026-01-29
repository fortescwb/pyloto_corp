"""Unit tests for session helpers: is_first_message_of_day and append_received_event."""
from datetime import datetime, timezone, timedelta

from pyloto_corp.application.session import SessionState
from pyloto_corp.application.session_helpers import (
    is_first_message_of_day,
    append_received_event,
)


def test_is_first_message_of_day_empty_history() -> None:
    session = SessionState(session_id="s1")
    now = int(datetime.now(tz=timezone.utc).timestamp())
    assert is_first_message_of_day(session, now) is True


def test_append_and_detect_same_day() -> None:
    session = SessionState(session_id="s2")
    now_dt = datetime.now(tz=timezone.utc)
    now = int(now_dt.timestamp())

    append_received_event(session, now)

    # Now second message same day should be False
    assert is_first_message_of_day(session, now) is False


def test_is_first_message_of_day_different_day() -> None:
    session = SessionState(session_id="s3")
    yesterday_dt = datetime.now(tz=timezone.utc) - timedelta(days=1)
    yesterday = int(yesterday_dt.timestamp())

    append_received_event(session, yesterday)

    # Now message today should be considered first of day
    today = int(datetime.now(tz=timezone.utc).timestamp())
    assert is_first_message_of_day(session, today) is True
