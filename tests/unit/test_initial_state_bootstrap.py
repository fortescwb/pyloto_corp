from __future__ import annotations

from pyloto_corp.application.pipeline import WhatsAppInboundPipeline
from pyloto_corp.application.session import SessionState
from pyloto_corp.domain.enums import Outcome
from pyloto_corp.domain.fsm.initial_state import INITIAL_STATE
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


class CapturingStateSelector:
    def __init__(self):
        self.last_prompt = None

    def complete(self, prompt, model=None):
        # Capture prompt so test can assert it contains initial state and possible next states
        self.last_prompt = prompt
        # Return a safe default (reject change)
        return {"selected_state": "INIT", "confidence": 0.0, "status": "in_progress"}


def test_new_session_has_explicit_initial_state():
    session = SessionState(session_id="s1")
    assert session.current_state == INITIAL_STATE.value


def test_existing_session_state_is_preserved():
    session = SessionState(session_id="s2")
    session.current_state = "COLLECTING_INFO"
    assert session.current_state == "COLLECTING_INFO"


def test_state_selector_receives_initial_state_and_next_states_in_prompt():
    llm = CapturingStateSelector()
    pipeline = WhatsAppInboundPipeline(
        dedupe_store=InMemoryDedupeStore(),
        session_store=InMemorySessionStore(),
        orchestrator=DummyOrchestrator(outcome=Outcome.AWAITING_USER),
        state_selector_client=llm,
    )

    msg = DummyMessage("olá, quero informação")
    # Call orchestration which triggers state selector
    pipeline._orchestrate_and_save(msg, SessionState(session_id="s3"))

    assert llm.last_prompt is not None
    # Must contain explicit current state value
    assert f"Estado atual: {INITIAL_STATE.value}" in llm.last_prompt
    # Must contain Próximos possíveis list (non empty)
    assert "Próximos possíveis:" in llm.last_prompt
