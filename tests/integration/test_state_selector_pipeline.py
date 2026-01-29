from __future__ import annotations

from pyloto_corp.application.pipeline import WhatsAppInboundPipeline
from pyloto_corp.application.session import SessionState
from pyloto_corp.domain.conversation_state import ConversationState
from pyloto_corp.domain.enums import Outcome
from pyloto_corp.infra.dedupe import InMemoryDedupeStore
from pyloto_corp.infra.session_store import InMemorySessionStore


class DummyMessage:
    def __init__(self, text: str, message_id: str = "msg1"):
        self.text = text
        self.message_id = message_id
        self.chat_id = "chat1"


class DummyOrchestrator:
    class Response:
        def __init__(self, outcome, reply=None, confidence=0.5):
            self.outcome = outcome
            self.reply_text = reply
            self.intent = None
            self.confidence = confidence

    def __init__(self, outcome):
        self._outcome = outcome

    def process_message(self, message, session=None, is_duplicate=False):
        return self.Response(self._outcome)


class AcceptingLLM:
    def complete(self, prompt, model=None):
        return {"selected_state": "HANDOFF_HUMAN", "confidence": 0.9, "status": "done"}


class RejectingLLM:
    def complete(self, prompt, model=None):
        return {"selected_state": "HANDOFF_HUMAN", "confidence": 0.4, "status": "in_progress"}


def test_pipeline_applies_state_when_accepted():
    pipeline = WhatsAppInboundPipeline(
        dedupe_store=InMemoryDedupeStore(),
        session_store=InMemorySessionStore(),
        orchestrator=DummyOrchestrator(outcome=Outcome.AWAITING_USER),
        state_selector_client=AcceptingLLM(),
    )
    msg = DummyMessage("quero falar com humano")
    result = pipeline._orchestrate_and_save(msg, SessionState(session_id="s1"))

    assert result.state_decision and result.state_decision.accepted is True
    assert result.state_decision.next_state == ConversationState.HANDOFF_HUMAN


def test_pipeline_keeps_state_when_rejected():
    pipeline = WhatsAppInboundPipeline(
        dedupe_store=InMemoryDedupeStore(),
        session_store=InMemorySessionStore(),
        orchestrator=DummyOrchestrator(outcome=Outcome.AWAITING_USER),
        state_selector_client=RejectingLLM(),
    )
    session = SessionState(session_id="s2")
    msg = DummyMessage("ok, obrigado")

    result = pipeline._orchestrate_and_save(msg, session)

    assert result.state_decision and result.state_decision.accepted is False
    assert session.current_state == "INIT"
    assert result.state_decision.response_hint
