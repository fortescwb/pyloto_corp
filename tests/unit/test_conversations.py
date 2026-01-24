from __future__ import annotations

from datetime import UTC, datetime

from pyloto_corp.application.conversations import (
    TEXT_MAX_LEN,
    TRUNCATION_MARKER,
    AppendMessageUseCase,
    sanitize_text,
)
from pyloto_corp.domain.conversations import (
    AppendResult,
    ConversationMessage,
    ConversationStore,
    Page,
)
from pyloto_corp.utils.ids import derive_user_key


class FakeConversationStore(ConversationStore):
    def __init__(self) -> None:
        self.messages: dict[str, ConversationMessage] = {}

    def append_message(self, message: ConversationMessage) -> AppendResult:
        if message.provider_message_id in self.messages:
            return AppendResult(created=False)
        self.messages[message.provider_message_id] = message
        return AppendResult(created=True)

    def get_messages(self, user_key: str, limit: int, cursor: str | None = None) -> Page:
        items = [msg for msg in self.messages.values() if msg.user_key == user_key][:limit]
        return Page(items=items, next_cursor=None)

    def get_header(self, user_key: str):
        return None


def test_derive_user_key_is_deterministic_and_not_phone():
    phone = "5511999999999"
    pepper = "pepper-secret"

    key1 = derive_user_key(phone, pepper)
    key2 = derive_user_key(phone, pepper)

    assert key1 == key2
    assert key1 != phone
    assert phone not in key1


def test_append_message_use_case_is_idempotent():
    store = FakeConversationStore()
    use_case = AppendMessageUseCase(store=store, pepper_secret="pepper")
    timestamp = datetime.now(tz=UTC)

    result1 = use_case.execute(
        phone_e164="5511999999999",
        provider_message_id="msg-1",
        direction="in",
        actor="USER",
        timestamp=timestamp,
        text="Oi",
    )
    result2 = use_case.execute(
        phone_e164="5511999999999",
        provider_message_id="msg-1",
        direction="in",
        actor="USER",
        timestamp=timestamp,
        text="Oi",
    )

    assert result1.created is True
    assert result2.created is False
    assert len(store.messages) == 1


def test_sanitize_text_normalizes_and_truncates():
    raw = "  hello   world  \n\n\n  line2\t\t"
    sanitized = sanitize_text(raw)
    assert sanitized == "hello world\n\nline2"

    long_text = "a" * (TEXT_MAX_LEN + 10)
    truncated = sanitize_text(long_text)
    assert len(truncated) == TEXT_MAX_LEN
    assert truncated.endswith(TRUNCATION_MARKER)
