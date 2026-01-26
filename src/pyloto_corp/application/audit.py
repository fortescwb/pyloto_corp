"""Casos de uso para trilha de auditoria."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from pyloto_corp.domain.audit import (
    AuditAction,
    AuditActor,
    AuditEvent,
    AuditLogStore,
    compute_event_hash,
)
from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class RecordAuditEventUseCase:
    """Append-only de eventos de auditoria com hash encadeado."""

    store: AuditLogStore
    max_retries: int = 3

    def execute(
        self,
        *,
        user_key: str,
        action: AuditAction,
        reason: str,
        actor: AuditActor = "SYSTEM",
        tenant_id: str | None = None,
        correlation_id: str | None = None,
    ) -> AuditEvent:
        """Registra evento com tolerância a concorrência."""

        for attempt in range(self.max_retries):
            latest = self.store.get_latest_event(user_key)
            prev_hash = latest.hash if latest else None

            event_hash_value = compute_event_hash(
                {
                    "event_id": str(uuid.uuid4()),
                    "user_key": user_key,
                    "tenant_id": tenant_id,
                    "timestamp": datetime.now(tz=UTC),
                    "actor": actor,
                    "action": action,
                    "reason": reason,
                    "prev_hash": prev_hash,
                    "correlation_id": correlation_id,
                },
                prev_hash,
            )
            event = AuditEvent(
                event_id=str(uuid.uuid4()),
                user_key=user_key,
                tenant_id=tenant_id,
                timestamp=datetime.now(tz=UTC),
                actor=actor,
                action=action,
                reason=reason,
                prev_hash=prev_hash,
                correlation_id=correlation_id,
                hash=event_hash_value,
            )

            success = self.store.append_event(event, expected_prev_hash=prev_hash)
            if success:
                logger.info(
                    "Audit event appended",
                    extra={
                        "user_key": user_key,
                        "event_id": event.event_id,
                        "action": action,
                        "actor": actor,
                        "attempt": attempt + 1,
                    },
                )
                return event

        raise RuntimeError("Falha ao registrar evento de auditoria após retries")
