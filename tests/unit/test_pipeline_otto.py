"""Tests to ensure Otto intro is applied on first message of the day."""

from datetime import UTC, datetime

from pyloto_corp.adapters.whatsapp.models import NormalizedWhatsAppMessage
from pyloto_corp.application.pipeline import WhatsAppInboundPipeline
from pyloto_corp.application.pipeline_config import PipelineConfig
from pyloto_corp.domain.constants.otto import OTTO_INTRO_TEXT
from pyloto_corp.infra.dedupe import InMemoryDedupeStore
from pyloto_corp.infra.session_store_memory import InMemorySessionStore


class DummyOrchestrator:
    def process_message(self, message, session=None, is_duplicate=False):
        from pyloto_corp.ai.orchestrator import AIResponse

        # Simple deterministic reply based on message text
        return AIResponse(reply_text=(message.text or ""), outcome=None)


def make_message(
    msg_text: str,
    ts: int,
    message_id: str = "m1",
    chat_id: str | None = None,
) -> NormalizedWhatsAppMessage:
    m = NormalizedWhatsAppMessage(
        message_id=message_id,
        from_number="5511999998888",
        timestamp=str(ts),
        message_type="text",
        text=msg_text,
    )
    if chat_id is not None:
        # chat_id is not a formal field of NormalizedWhatsAppMessage but
        # pipeline reads it via getattr.
        # Use object.__setattr__ to bypass Pydantic's field checks
        object.__setattr__(m, "chat_id", chat_id)
    return m


def test_otto_prefix_on_first_message_of_day() -> None:
    dedupe = InMemoryDedupeStore()
    session_store = InMemorySessionStore()
    orchestrator = DummyOrchestrator()

    config = PipelineConfig(
        dedupe_store=dedupe,
        session_store=session_store,
        orchestrator=orchestrator,
    )
    pipeline = WhatsAppInboundPipeline(config)

    init_msg = make_message("oi", str(int(datetime.now(tz=UTC).timestamp())))
    session = pipeline._get_or_create_session(init_msg, sender_phone=None)

    ts = int(datetime.now(tz=UTC).timestamp())
    # Tie message to the existing session by using session.session_id as chat_id
    msg = make_message("Olá Pyloto", ts, message_id="m1", chat_id=session.session_id)

    # Ensure helper considers this the first message of day for this session
    from pyloto_corp.application.session_helpers import is_first_message_of_day

    assert is_first_message_of_day(session, msg.timestamp)

    # Use _orchestrate_and_save directly to operate on the same session object
    processed = pipeline._orchestrate_and_save(msg, session)

    assert processed is not None
    assert processed.reply_text is not None
    assert processed.reply_text.startswith(OTTO_INTRO_TEXT)

    # Second message same day should not be prefixed when using same session
    msg2 = make_message("Outra pergunta", ts + 10, message_id="m2")
    processed2 = pipeline._orchestrate_and_save(msg2, session)
    assert processed2 is not None
    assert processed2.reply_text is not None
    assert not processed2.reply_text.startswith(OTTO_INTRO_TEXT)


def test_retry_same_message_id_does_not_duplicate_history() -> None:
    dedupe = InMemoryDedupeStore()
    session_store = InMemorySessionStore()
    orchestrator = DummyOrchestrator()

    config = PipelineConfig(
        dedupe_store=dedupe,
        session_store=session_store,
        orchestrator=orchestrator,
    )
    pipeline = WhatsAppInboundPipeline(config)

    init_msg = make_message("init", str(int(datetime.now(tz=UTC).timestamp())))
    session = pipeline._get_or_create_session(init_msg, sender_phone=None)

    ts = int(datetime.now(tz=UTC).timestamp())
    msg = make_message("Primeiro", ts, message_id="retry-1", chat_id=session.session_id)

    processed = pipeline._orchestrate_and_save(msg, session)
    assert processed.reply_text is not None
    assert processed.reply_text.startswith(OTTO_INTRO_TEXT)
    message_entries = [rec for rec in session.message_history if rec.get("message_id") == "retry-1"]
    assert len(message_entries) == 1

    processed_retry = pipeline._orchestrate_and_save(msg, session)
    assert processed_retry.reply_text is not None
    assert not processed_retry.reply_text.startswith(OTTO_INTRO_TEXT)
    message_entries = [rec for rec in session.message_history if rec.get("message_id") == "retry-1"]
    assert len(message_entries) == 1
