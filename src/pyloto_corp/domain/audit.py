"""Modelos e portas para trilha de auditoria (append-only)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel

AuditAction = Literal["USER_CONTACT", "EXPORT_GENERATED", "PROFILE_UPDATED", "NOTE_ADDED"]
AuditActor = Literal["SYSTEM", "HUMAN"]


class AuditEvent(BaseModel):
    """Evento de auditoria encadeado por hash."""

    event_id: str
    user_key: str
    tenant_id: str | None = None
    timestamp: datetime
    actor: AuditActor
    action: AuditAction
    reason: str
    prev_hash: str | None = None
    hash: str
    correlation_id: str | None = None


def compute_event_hash(event_data: dict[str, object], prev_hash: str | None) -> str:
    """Calcula SHA256 do json canônico + prev_hash (append-only).

    event_data não deve conter o campo "hash".
    """

    def _default(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)

    canonical = json.dumps(event_data, sort_keys=True, separators=(",", ":"), default=_default)
    payload = f"{canonical}{prev_hash or ''}".encode()
    return hashlib.sha256(payload).hexdigest()


@dataclass(slots=True)
class AuditLogStore(Protocol):
    """Porta para armazenamento de eventos de auditoria."""

    def get_latest_event(self, user_key: str) -> AuditEvent | None:
        """Retorna o último evento, se existir."""

    def list_events(self, user_key: str, limit: int = 500) -> list[AuditEvent]:
        """Lista eventos ordenados por timestamp asc."""

    def append_event(self, event: AuditEvent, expected_prev_hash: str | None) -> bool:
        """Append condicional; retorna False em conflito de cadeia."""
