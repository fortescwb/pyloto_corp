"""Export de histórico de conversas com auditoria."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from pyloto_corp.application.audit import RecordAuditEventUseCase
from pyloto_corp.domain.audit import AuditLogStore
from pyloto_corp.domain.conversations import ConversationMessage, ConversationStore
from pyloto_corp.domain.profile import UserProfile, UserProfileStore
from pyloto_corp.infra.secrets import get_pepper_secret
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
    conversation_store: ConversationStore
    profile_store: UserProfileStore
    audit_store: AuditLogStore
    history_exporter: HistoryExporterProtocol
    audit_recorder: RecordAuditEventUseCase
    default_include_pii: bool = False
    timezone: str = "America/Sao_Paulo"

    def _get_messages(self, user_key: str) -> list[ConversationMessage]:
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

    def _render_messages(
        self,
        messages: Iterable[ConversationMessage],
        tz: ZoneInfo,
        phone: str | None,
        include_pii: bool,
    ) -> list[str]:
        lines: list[str] = []
        for msg in messages:
            local_ts = msg.timestamp.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S %z")
            actor_label = msg.actor
            if include_pii and msg.actor == "USER" and phone:
                actor_label = f"USER({phone})"
            lines.append(f"[{local_ts}] {actor_label} - {msg.text}")
        return lines

    def _render_audit(self, events, tz: ZoneInfo) -> list[str]:
        lines: list[str] = []
        for ev in events:
            local_ts = ev.timestamp.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S %z")
            lines.append(
                f"[{local_ts}] {ev.action} {ev.actor} {ev.reason} "
                f"{ev.event_id} {ev.hash} prev={ev.prev_hash}"
            )
        return lines

    def _render_profile(self, profile: UserProfile | None, include_pii: bool) -> list[str]:
        lines: list[str] = []
        if not profile:
            lines.append("N/A")
            return lines

        if include_pii:
            lines.append(f"Telefone: {profile.phone_e164}")
        lines.append(f"Display Name: {profile.display_name or 'N/A'}")
        for key in sorted(profile.collected_fields.keys()):
            lines.append(f"{key}: {profile.collected_fields.get(key)}")
        return lines

    def _build_header(
        self,
        user_key: str,
        profile: UserProfile | None,
        phone_to_render: str | None,
        generated_at: datetime,
        tz: ZoneInfo,
    ) -> list[str]:
        """Constrói linhas de cabeçalho do export.

        Args:
            user_key: Chave de usuário
            profile: Perfil do usuário (pode ser None)
            phone_to_render: Telefone para incluir (se PII aprovado)
            generated_at: Timestamp de geração
            tz: Timezone para localização

        Returns:
            Lista de linhas de cabeçalho
        """
        header_lines = [
            "HISTÓRICO DE CONVERSA — Pyloto",
            (
                f"Usuário: "
                f"{profile.display_name if profile and profile.display_name else 'N/A'}"
            ),
        ]
        if phone_to_render:
            header_lines.append(f"Telefone: {phone_to_render}")
        
        generated_ts = generated_at.astimezone(tz)
        generated_local = generated_ts.strftime("%Y-%m-%d %H:%M:%S %z")
        header_lines.extend([
            f"UserKey: {user_key}",
            f"Gerado em: {generated_local} / {generated_at.isoformat()}",
        ])
        return header_lines

    def _format_export_text(
        self,
        header_lines: list[str],
        profile_lines: list[str],
        message_lines: list[str],
        audit_lines: list[str],
    ) -> str:
        """Formata todos os dados do export em texto único.

        Args:
            header_lines: Cabeçalho
            profile_lines: Linhas de perfil
            message_lines: Linhas de mensagens
            audit_lines: Linhas de auditoria

        Returns:
            Texto formatado pronto para persistência
        """
        export_parts = [
            "\n".join(header_lines),
            "\nDADOS COLETADOS",
            "\n".join(profile_lines) if profile_lines else "N/A",
            "\nMENSAGENS",
            "\n".join(message_lines),
            "\nAUDITORIA (APPEND-ONLY)",
            "\n".join(audit_lines),
        ]
        return "\n".join(export_parts)

    def _record_export_event(
        self,
        user_key: str,
        requester_actor: str,
        reason: str,
        tenant_id: str | None,
    ) -> str:
        """Registra evento de export na auditoria.

        Args:
            user_key: Chave de usuário
            requester_actor: Quem solicitou o export
            reason: Razão do export
            tenant_id: ID do tenant (opcional)

        Returns:
            Hash do evento de auditoria
        """
        export_event = self.audit_recorder.execute(
            user_key=user_key,
            action="EXPORT_GENERATED",
            reason=reason,
            actor=requester_actor,  # type: ignore[arg-type]
            tenant_id=tenant_id,
        )
        return export_event.hash

    def execute(
        self,
        *,
        phone_e164: str | None = None,
        user_key: str | None = None,
        include_pii: bool | None = None,
        requester_actor: str = "SYSTEM",
        reason: str,
        tenant_id: str | None = None,
    ) -> ExportResult:
        """Executa export de histórico de conversa.

        Orquestra coleta, formatação, persistência e auditoria.

        Args:
            phone_e164: Telefone do usuário (se user_key não fornecido)
            user_key: Chave de usuário
            include_pii: Se deve incluir PII no export
            requester_actor: Ator que solicitou (padrão: SYSTEM)
            reason: Razão do export (auditoria)
            tenant_id: ID do tenant (opcional)

        Returns:
            ExportResult com texto, caminho e metadados

        Raises:
            ValueError: Se nem phone_e164 nem user_key forem fornecidos
        """
        # Determinar user_key e PII
        include_pii = (
            include_pii
            if include_pii is not None
            else self.default_include_pii
        )

        if not user_key:
            if not phone_e164:
                raise ValueError(
                    "phone_e164 ou user_key deve ser informado"
                )
            pepper = get_pepper_secret()
            user_key = derive_user_key(phone_e164, pepper)

        tz = ZoneInfo(self.timezone)

        # 1. Coletar dados do armazenamento
        data = self._collect_export_data(user_key, include_pii)

        # 2. Renderizar e formatar dados em texto
        text = self._render_export_text(
            data, tz, user_key, include_pii
        )

        # 3-4. Persistir export e registrar auditoria
        path, audit_hash = self._persist_export_and_audit(
            user_key, text, requester_actor, reason, tenant_id
        )

        # 5. Compilar resultado final
        result = self._compile_export_result(
            text, path, user_key, data, audit_hash
        )

        return result

    def _collect_export_data(
        self, user_key: str, include_pii: bool
    ) -> dict[str, Any]:
        """Coleta dados de conversas, perfil e auditoria.

        Args:
            user_key: Chave de usuário
            include_pii: Se inclui PII no resultado

        Returns:
            Dicionário com profile, messages e audit_events
        """
        profile = self.profile_store.get_profile(user_key)
        phone_to_render = (
            profile.phone_e164 if (profile and include_pii) else None
        )
        messages = self._get_messages(user_key)
        audit_events = self.audit_store.list_events(user_key)

        return {
            "profile": profile,
            "phone_to_render": phone_to_render,
            "messages": messages,
            "audit_events": audit_events,
        }

    def _render_export_text(
        self,
        data: dict[str, Any],
        tz: ZoneInfo,
        user_key: str,
        include_pii: bool,
    ) -> str:
        """Renderiza e formata dados em texto de export.

        Args:
            data: Dados coletados (profile, messages, audit_events)
            tz: Timezone para localização
            user_key: Chave de usuário
            include_pii: Se inclui PII

        Returns:
            Texto formatado pronto para persistência
        """
        generated_at = datetime.now(tz=UTC)

        message_lines = self._render_messages(
            data["messages"], tz, data["phone_to_render"], include_pii
        )
        audit_lines = self._render_audit(data["audit_events"], tz)
        profile_lines = self._render_profile(data["profile"], include_pii)

        header_lines = self._build_header(
            user_key,
            data["profile"],
            data["phone_to_render"],
            generated_at,
            tz,
        )

        export_text = self._format_export_text(
            header_lines, profile_lines, message_lines, audit_lines
        )

        return export_text

    def _persist_export_and_audit(
        self,
        user_key: str,
        export_text: str,
        requester_actor: str,
        reason: str,
        tenant_id: str | None,
    ) -> tuple[str, str]:
        """Persiste export e registra auditoria.

        Args:
            user_key: Chave de usuário
            export_text: Texto do export
            requester_actor: Ator que solicitou
            reason: Razão do export
            tenant_id: ID do tenant

        Returns:
            Tupla (path, audit_hash)
        """
        # Persistir export
        path = self.history_exporter.save(
            user_key=user_key,
            content=export_text.encode("utf-8"),
            content_type="text/plain",
        )

        # Registrar auditoria
        audit_hash = self._record_export_event(
            user_key, requester_actor, reason, tenant_id
        )

        return path, audit_hash

    def _compile_export_result(
        self,
        export_text: str,
        path: str,
        user_key: str,
        data: dict[str, Any],
        audit_hash: str,
    ) -> ExportResult:
        """Compila resultado final com metadados.

        Args:
            export_text: Texto do export
            path: Caminho de persistência
            user_key: Chave de usuário
            data: Dados coletados
            audit_hash: Hash do evento de auditoria

        Returns:
            ExportResult com metadados
        """
        export_hash = hashlib.sha256(
            export_text.encode("utf-8")
        ).hexdigest()

        metadata = {
            "user_key": user_key,
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "message_count": len(data["messages"]),
            "audit_tail_hash": audit_hash,
            "sha256_of_export": export_hash,
            "export_path": path,
        }

        logger.info(
            "Conversation export generated",
            extra={
                "user_key": user_key,
                "message_count": len(data["messages"]),
                "audit_tail_hash": metadata["audit_tail_hash"],
            },
        )

        return ExportResult(
            export_text=export_text, export_path=path, metadata=metadata
        )
