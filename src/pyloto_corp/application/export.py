"""Export de histórico de conversas com auditoria.

Responsabilidades:
- Orquestar coleta, renderização, persistência e auditoria de export
- Manter injeção de dependências (sem imports de infra)
- Validar parâmetros de entrada

Conforme regras_e_padroes.md (SRP, injeção de dep., <200 linhas).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from pyloto_corp.application.audit import RecordAuditEventUseCase
from pyloto_corp.application.renderers.export_renderers import (
    build_header,
    format_export_text,
    render_audit,
    render_messages,
    render_profile,
)
from pyloto_corp.domain.audit import AuditEvent, AuditLogStore
from pyloto_corp.domain.conversations import ConversationStore
from pyloto_corp.domain.profile import UserProfileStore
from pyloto_corp.domain.secret_provider import SecretProvider
from pyloto_corp.observability.logging import get_logger
from pyloto_corp.utils.ids import derive_user_key

logger = get_logger(__name__)


class HistoryExporterProtocol:
    """Porta para salvar export (ex.: GCS)."""

    def save(
        self,
        *,
        user_key: str,
        content: bytes,
        content_type: str = "text/plain",
    ) -> str:
        """Persiste e retorna path/uri interno (não público)."""


@dataclass(slots=True)
class ExportResult:
    export_text: str
    export_path: str
    metadata: dict


@dataclass(slots=True)
class ExportConversationUseCase:
    """Orquestra export de conversa — Injeção de dependências obrigatória."""

    conversation_store: ConversationStore
    profile_store: UserProfileStore
    audit_store: AuditLogStore
    history_exporter: HistoryExporterProtocol
    audit_recorder: RecordAuditEventUseCase
    secret_provider: SecretProvider  # ← INJETAR, não importar infra
    default_include_pii: bool = False
    timezone: str = "America/Sao_Paulo"

    def _get_messages(self, user_key: str) -> list:
        """Coleta todas as mensagens da conversa."""
        from pyloto_corp.domain.conversations import ConversationMessage

        cursor = None
        all_messages: list[ConversationMessage] = []
        while True:
            page = self.conversation_store.get_messages(
                user_key=user_key, limit=200, cursor=cursor
            )
            all_messages.extend(page.items)
            if not page.next_cursor:
                break
            cursor = page.next_cursor
        all_messages.sort(key=lambda m: m.timestamp)
        return all_messages

    def _record_export_event(
        self,
        user_key: str,
        requester_actor: str,
        reason: str,
        tenant_id: str | None,
    ) -> AuditEvent:
        """Registra evento de export na auditoria e retorna o evento."""
        actor_normalized = "SYSTEM" if requester_actor.upper() == "SYSTEM" else "HUMAN"
        export_event = self.audit_recorder.execute(
            user_key=user_key,
            action="EXPORT_GENERATED",
            reason=reason,
            actor=actor_normalized,
            tenant_id=tenant_id,
        )
        return export_event

    def _collect_data(
        self, user_key: str, include_pii: bool
    ) -> tuple[Any, str | None, list]:
        """Coleta profile e mensagens necessárias para o export."""
        profile = self.profile_store.get_profile(user_key)
        phone_render = profile.phone_e164 if (profile and include_pii) else None
        messages = self._get_messages(user_key)
        return profile, phone_render, messages

    def _render_export(
        self,
        user_key: str,
        profile: Any,
        phone_render: str | None,
        messages: list,
        audit_events: list,
        include_pii: bool,
        tz: ZoneInfo,
    ) -> str:
        """Renderiza texto do export."""
        msg_lines = render_messages(messages, tz, phone_render, include_pii)
        audit_lines = render_audit(audit_events, tz)
        profile_lines = render_profile(profile, include_pii)
        header_lines = build_header(
            user_key, profile, phone_render, datetime.now(tz=UTC), tz
        )
        return format_export_text(header_lines, profile_lines, msg_lines, audit_lines)

    def _build_metadata(
        self,
        user_key: str,
        messages: list,
        audit_hash: str,
        export_text: str,
        export_path: str,
    ) -> dict:
        """Compila metadata do export."""
        export_hash = hashlib.sha256(export_text.encode("utf-8")).hexdigest()
        return {
            "user_key": user_key,
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "message_count": len(messages),
            "audit_tail_hash": audit_hash,
            "sha256_of_export": export_hash,
            "export_path": export_path,
        }

    def _resolve_user_key(self, phone_e164: str | None, user_key: str | None) -> str:
        """Resolve user_key a partir de phone_e164 se necessário."""
        if user_key:
            return user_key
        if not phone_e164:
            raise ValueError("phone_e164 ou user_key deve ser informado")
        pepper = self.secret_provider.get_pepper_secret()
        return derive_user_key(phone_e164, pepper)

    def execute(
        self,
        *,
        phone_e164: str | None = None,
        user_key: str | None = None,
        include_pii: bool | None = None,
        requester_actor: str = "SYSTEM",
        reason: str,
        tenant_id: str | None = None,
        timezone: str | None = None,
    ) -> ExportResult:
        """Orquestra export — valida entrada, coleta, renderiza, persiste."""
        include_pii = self._resolve_include_pii(include_pii)
        user_key = self._resolve_user_key(phone_e164, user_key)
        tz = ZoneInfo(timezone or self.timezone)

        export_event = self._record_export_event(
            user_key, requester_actor, reason, tenant_id
        )
        profile, phone_render, messages = self._collect_data(user_key, include_pii)
        audit_events = [export_event]
        export_text = self._render_export(
            user_key, profile, phone_render, messages, audit_events, include_pii, tz
        )
        export_path = self._persist_export(user_key, export_text)
        metadata = self._build_metadata(
            user_key, messages, export_event.hash, export_text, export_path
        )
        self._log_generated_export(user_key, messages, export_event.hash)
        return ExportResult(
            export_text=export_text, export_path=export_path, metadata=metadata
        )

    def _resolve_include_pii(self, include_pii: bool | None) -> bool:
        """Resolve flag include_pii com default configurado."""
        return include_pii if include_pii is not None else self.default_include_pii

    def _persist_export(self, user_key: str, export_text: str) -> str:
        """Salva export no history_exporter configurado."""
        return self.history_exporter.save(
            user_key=user_key,
            content=export_text.encode("utf-8"),
            content_type="text/plain",
        )

    def _log_generated_export(
        self, user_key: str, messages: list, audit_hash: str
    ) -> None:
        """Log estruturado do resultado do export."""
        logger.info(
            "Conversation export generated",
            extra={
                "user_key": user_key,
                "message_count": len(messages),
                "audit_tail_hash": audit_hash,
            },
        )
