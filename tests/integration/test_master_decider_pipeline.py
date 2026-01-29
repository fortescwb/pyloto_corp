from __future__ import annotations

from unittest.mock import MagicMock

from pyloto_corp.application.pipeline import WhatsAppInboundPipeline
from pyloto_corp.application.session import SessionState
from pyloto_corp.domain.conversation_state import (
    ConversationState,
    StateSelectorOutput,
    StateSelectorStatus,
)
from pyloto_corp.domain.enums import MessageType, Outcome
from pyloto_corp.infra.dedupe import InMemoryDedupeStore
from pyloto_corp.infra.session_store import InMemorySessionStore


class DummyMessage:
    def __init__(self, text: str, message_id: str = "msg-final"):
        self.text = text
        self.message_id = message_id
        self.chat_id = "chat-final"


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


class PassLLM:
    def complete(self, prompt, model=None, timeout=None):
        return {
            "final_state": "HANDOFF_HUMAN",
            "apply_state": True,
            "selected_response_index": 1,
            "message_type": "text",
            "overall_confidence": 0.9,
            "reason": "ok",
        }


def _state_decision():
    return StateSelectorOutput(
        selected_state=ConversationState.HANDOFF_HUMAN,
        confidence=0.8,
        accepted=True,
        next_state=ConversationState.HANDOFF_HUMAN,
        response_hint=None,
        status=StateSelectorStatus.DONE,
    )


def test_pipeline_runs_master_decider_and_persists_audit():
    audit = MagicMock()
    pipeline = WhatsAppInboundPipeline(
        dedupe_store=InMemoryDedupeStore(),
        session_store=InMemorySessionStore(),
        orchestrator=DummyOrchestrator(outcome=Outcome.AWAITING_USER),
        state_selector_client=lambda *args, **kwargs: {
            "selected_state": "HANDOFF_HUMAN",
            "confidence": 0.9,
            "status": "done",
        },
        response_generator_client=lambda *args, **kwargs: {
            "responses": ["r1", "r2", "r3"],
            "response_style_tags": [],
            "chosen_index": 0,
            "safety_notes": [],
        },
        master_decider_client=PassLLM(),
        decision_audit_store=audit,
    )
    session = SessionState(session_id="sess")
    msg = DummyMessage("quero falar com humano")

    result = pipeline._orchestrate_and_save(msg, session)

    assert result.master_decision is not None
    assert result.selected_response_text == "r2"
    assert result.message_type == MessageType.TEXT
    assert session.current_state == ConversationState.HANDOFF_HUMAN.value
    audit.append.assert_called_once()
