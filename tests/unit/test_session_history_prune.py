from __future__ import annotations

from pyloto_corp.application.session import SessionState
from pyloto_corp.application.session_helpers import append_received_event
from pyloto_corp.config.settings import get_settings


def test_append_prunes_history_and_keeps_last_entry(caplog):
    settings = get_settings()
    # ajusta para teste
    settings.SESSION_MESSAGE_HISTORY_MAX_ENTRIES = 5

    session = SessionState(session_id="s-prune")

    # Adiciona 7 entradas (N + 2)
    for i in range(7):
        append_received_event(session, i, correlation_id=f"m{i}")

    assert len(session.message_history) == 5
    # ultima inserida deve estar presente
    assert session.message_history[-1]["received_at"] is not None
    # log de poda emitido
    found = any(r.message == "session_history_pruned" for r in caplog.records)
    assert found


def test_prune_logs_structured_fields(caplog):
    settings = get_settings()
    settings.SESSION_MESSAGE_HISTORY_MAX_ENTRIES = 3

    session = SessionState(session_id="s-prune-2")
    append_received_event(session, 1, correlation_id="cid1")
    append_received_event(session, 2, correlation_id="cid2")
    append_received_event(session, 3, correlation_id="cid3")
    # This will prune
    append_received_event(session, 4, correlation_id="cid4")

    recs = [r for r in caplog.records if r.message == "session_history_pruned"]
    assert recs, "expected a prune log"
    r = recs[-1]
    assert getattr(r, "session_history_pruned", None) is True
    assert getattr(r, "max_entries", None) == 3
    assert getattr(r, "previous_len", None) >= getattr(r, "new_len", None)
    assert getattr(r, "correlation_id", None) == "cid4"
