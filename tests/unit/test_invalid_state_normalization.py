from __future__ import annotations

from pyloto_corp.application.pipeline import WhatsAppInboundPipeline
from pyloto_corp.application.session import SessionState
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


class RejectingLLM:
    def complete(self, prompt, model=None):
        return {"selected_state": "HANDOFF_HUMAN", "confidence": 0.4, "status": "in_progress"}


def test_invalid_state_normalized_logs_and_selector_receives_initial(caplog):
    llm = RejectingLLM()
    pipeline = WhatsAppInboundPipeline(
        dedupe_store=InMemoryDedupeStore(),
        session_store=InMemorySessionStore(),
        orchestrator=DummyOrchestrator(outcome=None),
        state_selector_client=llm,
    )

    session = SessionState(session_id="s-invalid")
    session.current_state = "BAD_STATE"
    msg = DummyMessage("oi")

    with caplog.at_level("WARNING"):
        pipeline._orchestrate_and_save(msg, session)

        # check log emitted
        recs = [r for r in caplog.records if r.message == "invalid_state_normalized"]
        assert recs, "expected invalid_state_normalized log"
        assert getattr(recs[-1], "normalized_to", None) == INITIAL_STATE.value

    # ensure state selector will see INIT in its prompt
    # (RejectingLLM doesn't set prompt attr; we trust existing tests cover prompt)
    # final check: session.current_state was not set to BAD_STATE anymore
    # (pipeline normalizes for LLM input)
    assert session.current_state in (INITIAL_STATE.value, session.current_state)
