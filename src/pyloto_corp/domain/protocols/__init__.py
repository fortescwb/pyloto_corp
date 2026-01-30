"""Re-exports dos Protocolos de domínio para uso por Application."""

from __future__ import annotations

from pyloto_corp.domain.protocols.decision_audit_store import DecisionAuditStoreProtocol
from pyloto_corp.domain.protocols.dedupe import DedupeProtocol
from pyloto_corp.domain.protocols.session_store import (
    AsyncSessionStoreProtocol,
    SessionStoreProtocol,
)

__all__ = [
    "DedupeProtocol",
    "SessionStoreProtocol",
    "AsyncSessionStoreProtocol",
    "DecisionAuditStoreProtocol",
]
