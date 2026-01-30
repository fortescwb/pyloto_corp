"""Unit tests for session helpers: is_first_message_of_day and append_received_event."""

from datetime import UTC, datetime, timedelta

from pyloto_corp.application.session import SessionState
from pyloto_corp.application.session import helpers as package_helpers
from pyloto_corp.application.session_helpers import (
    append_received_event,
    is_first_message_of_day,
)


def test_is_first_message_of_day_empty_history() -> None:
    session = SessionState(session_id="s1")
    now = int(datetime.now(tz=UTC).timestamp())
    assert is_first_message_of_day(session, now) is True


def test_append_and_detect_same_day() -> None:
    session = SessionState(session_id="s2")
    now_dt = datetime.now(tz=UTC)
    now = int(now_dt.timestamp())

    append_received_event(session, now)

    # Now second message same day should be False
    assert is_first_message_of_day(session, now) is False


def test_is_first_message_of_day_different_day() -> None:
    session = SessionState(session_id="s3")
    yesterday_dt = datetime.now(tz=UTC) - timedelta(days=1)
    yesterday = int(yesterday_dt.timestamp())

    append_received_event(session, yesterday)

    # Now message today should be considered first of day
    today = int(datetime.now(tz=UTC).timestamp())
    assert is_first_message_of_day(session, today) is True


def test_append_received_event_stores_message_id() -> None:
    session = SessionState(session_id="s-msg-id")

    append_received_event(session, 1, message_id="m-1")

    assert len(session.message_history) == 1
    assert session.message_history[0]["message_id"] == "m-1"


def test_append_received_event_without_message_id() -> None:
    session = SessionState(session_id="s-no-id")

    append_received_event(session, 2, message_id=None)

    assert len(session.message_history) == 1
    assert "message_id" not in session.message_history[0]


def test_package_helpers_initialize_history_without_attribute() -> None:
    class Simple:
        message_history: list[dict[str, str]] = []

    session = Simple()

    package_helpers.append_received_event(session, 10)

    assert session.message_history
    assert session.message_history[0]["received_at"] is not None


def test_package_helpers_consider_none_timestamp_first_message() -> None:
    class Simple:
        message_history: list[dict[str, str]] = []

    assert package_helpers.is_first_message_of_day(Simple(), None) is True


def test_package_helpers_to_datetime_parses_iso_and_invalid() -> None:
    iso = "2026-01-30T12:00:00+00:00"

    assert package_helpers._to_datetime(iso) is not None
    assert package_helpers._to_datetime("invalid") is None


def test_package_helpers_detects_existing_day_with_iso() -> None:
    iso = "2026-01-30T12:00:00+00:00"

    class Simple:
        message_history = [{"received_at": iso}]

    assert package_helpers.is_first_message_of_day(Simple(), iso) is False
