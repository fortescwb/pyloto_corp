"""Testes mínimos de compatibilidade entre infra e domain protocols."""

from pyloto_corp.domain.protocols import (
    DecisionAuditStoreProtocol,
    DedupeProtocol,
    SessionStoreProtocol,
)
from pyloto_corp.infra import (
    DecisionAuditStore,
    DedupeStore,
    SessionStore,
)


def test_dedupe_implements_protocol() -> None:
    assert issubclass(DedupeStore, DedupeProtocol)


def test_session_store_implements_protocol() -> None:
    assert issubclass(SessionStore, SessionStoreProtocol)


def test_decision_audit_store_implements_protocol() -> None:
    assert issubclass(DecisionAuditStore, DecisionAuditStoreProtocol)
