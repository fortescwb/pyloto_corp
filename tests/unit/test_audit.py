from __future__ import annotations

from pyloto_corp.application.audit import RecordAuditEventUseCase
from pyloto_corp.domain.audit import AuditEvent, AuditLogStore


class FakeAuditStore(AuditLogStore):
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def get_latest_event(self, user_key: str) -> AuditEvent | None:
        candidates = [e for e in self.events if e.user_key == user_key]
        return candidates[-1] if candidates else None

    def list_events(self, user_key: str, limit: int = 500) -> list[AuditEvent]:
        return [e for e in self.events if e.user_key == user_key][:limit]

    def append_event(self, event: AuditEvent, expected_prev_hash: str | None) -> bool:
        latest = self.get_latest_event(event.user_key)
        latest_hash = latest.hash if latest else None
        if latest_hash != expected_prev_hash:
            return False
        self.events.append(event)
        return True


def test_hash_chain_links_prev_hash():
    store = FakeAuditStore()
    use_case = RecordAuditEventUseCase(store=store)

    ev1 = use_case.execute(user_key="u1", action="USER_CONTACT", reason="re-engaged")
    ev2 = use_case.execute(user_key="u1", action="EXPORT_GENERATED", reason="export")

    assert ev2.prev_hash == ev1.hash
    assert ev2.hash != ev1.hash
    assert len(store.events) == 2
