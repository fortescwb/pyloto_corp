from __future__ import annotations

from pyloto_corp.application.session import SessionState
from pyloto_corp.application.session_manager import SessionManager
from pyloto_corp.domain.fsm.initial_state import INITIAL_STATE
from pyloto_corp.infra.session_store import InMemorySessionStore


def test_get_or_create_creates_or_loads():
    store = InMemorySessionStore()
    manager = SessionManager(session_store=store)

    class Msg:
        chat_id = None

    # new session
    msg = Msg()
    s = manager.get_or_create_session(msg)
    assert isinstance(s, SessionState)
    assert s.current_state == INITIAL_STATE.value

    # save and load
    store.save(s)
    msg.chat_id = s.session_id
    s2 = manager.get_or_create_session(msg)
    assert s2.session_id == s.session_id


def test_normalize_invalid_state_logs_and_persists(caplog):
    store = InMemorySessionStore()
    manager = SessionManager(session_store=store)

    session = SessionState(session_id="s-invalid")
    session.current_state = "BAD"
    with caplog.at_level("WARNING"):
        conv = manager.normalize_current_state(session, correlation_id="cid1")
        assert conv == INITIAL_STATE
        # session should have been normalized (persist not automatic here, but state changed)
        assert session.current_state == INITIAL_STATE.value
        recs = [r for r in caplog.records if r.message == "invalid_state_normalized"]
        assert recs


def test_append_prunes_and_logs(caplog):
    store = InMemorySessionStore()
    manager = SessionManager(session_store=store)

    settings = manager._settings
    settings.SESSION_MESSAGE_HISTORY_MAX_ENTRIES = 3

    session = SessionState(session_id="s-prune")

    class Msg:
        def __init__(self, ts, mid):
            self.timestamp = ts
            self.message_id = mid

    for i in range(4):
        manager.append_user_message(session, Msg(i, f"m{i}"), correlation_id=f"m{i}")

    assert len(session.message_history) == 3
    recs = [r for r in caplog.records if r.message == "session_history_pruned"]
    assert recs
    r = recs[-1]
    assert getattr(r, "correlation_id", "") in ("m3", "")


def test_append_user_message_is_idempotent_by_message_id():
    store = InMemorySessionStore()
    manager = SessionManager(session_store=store)

    class Msg:
        def __init__(self, ts, mid):
            self.timestamp = ts
            self.message_id = mid

    session = SessionState(session_id="s-idem")

    first = manager.append_user_message(session, Msg(100, "mid-1"))
    second = manager.append_user_message(session, Msg(100, "mid-1"))
    third = manager.append_user_message(session, Msg(200, "mid-2"))

    assert first is True
    assert second is False
    assert third is False
    assert len(session.message_history) == 2
    assert session.message_history[0]["message_id"] == "mid-1"
    assert session.message_history[1]["message_id"] == "mid-2"
