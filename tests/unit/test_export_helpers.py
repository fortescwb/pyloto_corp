"""Helpers e fixtures para testes de export."""

from __future__ import annotations

from datetime import UTC, datetime

from pyloto_corp.application.audit import RecordAuditEventUseCase
from pyloto_corp.application.export import (
    ExportConversationUseCase,
    HistoryExporterProtocol,
)
from pyloto_corp.domain.audit import AuditEvent, AuditLogStore, compute_event_hash
from pyloto_corp.domain.conversations import (
    ConversationMessage,
    ConversationStore,
    Page,
)
from pyloto_corp.domain.profile import UserProfile, UserProfileStore


class FakeConversationStore(ConversationStore):
    """Mock de ConversationStore para testes."""

    def __init__(self, messages: list[ConversationMessage]) -> None:
        self._messages = messages

    def append_message(self, message: ConversationMessage):
        raise NotImplementedError

    def get_messages(
        self, user_key: str, limit: int, cursor: str | None = None
    ) -> Page:
        filtered = [m for m in self._messages if m.user_key == user_key]
        return Page(items=filtered, next_cursor=None)

    def get_header(self, user_key: str):
        return None


class FakeProfileStore(UserProfileStore):
    """Mock de UserProfileStore para testes."""

    def __init__(self, profile: UserProfile | None) -> None:
        self.profile = profile

    def get_profile(self, user_key: str) -> UserProfile | None:
        return (
            self.profile
            if self.profile and self.profile.user_key == user_key
            else None
        )

    def upsert_profile(self, profile: UserProfile) -> None:
        self.profile = profile


class FakeAuditStore(AuditLogStore):
    """Mock de AuditLogStore para testes."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def get_latest_event(self, user_key: str) -> AuditEvent | None:
        candidates = [e for e in self.events if e.user_key == user_key]
        return candidates[-1] if candidates else None

    def list_events(
        self, user_key: str, limit: int = 500
    ) -> list[AuditEvent]:
        return [e for e in self.events if e.user_key == user_key][:limit]

    def append_event(
        self, event: AuditEvent, expected_prev_hash: str | None
    ) -> bool:
        latest = self.get_latest_event(event.user_key)
        latest_hash = latest.hash if latest else None
        if latest_hash != expected_prev_hash:
            return False
        self.events.append(event)
        return True


class FakeExporter(HistoryExporterProtocol):
    """Mock de HistoryExporterProtocol para testes."""

    def __init__(self) -> None:
        self.saved: dict[str, bytes] = {}

    def save(
        self,
        *,
        user_key: str,
        content: bytes,
        content_type: str = "text/plain",
    ) -> str:
        path = f"mem://{user_key}/export.txt"
        self.saved[path] = content
        return path


def make_event(
    user_key: str,
    action: str,
    reason: str,
    prev_hash: str | None = None,
) -> AuditEvent:
    """Constrói um evento de auditoria para testes.

    Args:
        user_key: Chave do usuário
        action: Ação realizada
        reason: Razão da ação
        prev_hash: Hash anterior (para cadeia)

    Returns:
        AuditEvent construído e assinado
    """
    data = {
        "event_id": "evt-1",
        "user_key": user_key,
        "tenant_id": None,
        "timestamp": datetime.now(tz=UTC),
        "actor": "SYSTEM",
        "action": action,
        "reason": reason,
        "prev_hash": prev_hash,
        "correlation_id": None,
    }
    return AuditEvent(**data, hash=compute_event_hash(data, prev_hash))


def create_export_use_case(
    messages: list[ConversationMessage],
    profile: UserProfile | None,
) -> ExportConversationUseCase:
    """Constrói ExportConversationUseCase com mocks.

    Args:
        messages: Lista de mensagens
        profile: Perfil do usuário

    Returns:
        ExportConversationUseCase pronto para testes
    """
    conv_store = FakeConversationStore(messages)
    profile_store = FakeProfileStore(profile)
    audit_store = FakeAuditStore()
    exporter = FakeExporter()
    audit_recorder = RecordAuditEventUseCase(store=audit_store)

    return ExportConversationUseCase(
        conversation_store=conv_store,
        profile_store=profile_store,
        audit_store=audit_store,
        history_exporter=exporter,
        audit_recorder=audit_recorder,
        default_include_pii=False,
    )
