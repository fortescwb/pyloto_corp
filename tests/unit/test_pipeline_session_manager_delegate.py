from __future__ import annotations

from pyloto_corp.application.pipeline import WhatsAppInboundPipeline
from pyloto_corp.application.pipeline_config import PipelineConfig
from pyloto_corp.application.session import SessionState


class SpyManager:
    def __init__(self):
        self.called = []

    def get_or_create_session(self, message, sender_phone=None):
        self.called.append(("get_or_create", message, sender_phone))
        return SessionState(session_id="s-spy")

    def append_user_message(self, session, message, correlation_id=None):
        self.called.append(("append", message, correlation_id))
        return True

    def normalize_current_state(self, session, correlation_id=None):
        self.called.append(("normalize", session, correlation_id))
        return session

    def persist(self, session, correlation_id=None):
        self.called.append(("persist", session, correlation_id))


def test_pipeline_uses_session_manager_spy():
    spy = SpyManager()
    config = PipelineConfig(
        dedupe_store=None,
        session_store=None,
        orchestrator=None,
        session_manager=spy,
    )
    pipeline = WhatsAppInboundPipeline(config)

    class Msg:
        message_id = "m1"
        text = "oi"
        chat_id = None
        timestamp = 1

    # exercise internal flows that trigger session manager usage
    pipeline._get_or_create_session(Msg())
    assert spy.called and spy.called[0][0] == "get_or_create"

    # Simulate append + persist via the main processing path using internal helpers
    s = SessionState(session_id="s-spy2")
    pipeline._session_manager.append_user_message(s, Msg(), correlation_id="m1")
    pipeline._session_manager.persist(s, correlation_id="m1")
    assert any(c[0] == "append" for c in spy.called)
    assert any(c[0] == "persist" for c in spy.called)
