"""Renderizadores de Export — Formatação de Dados para Texto.

Responsabilidades:
- Renderizar mensagens com timestamps localizados
- Renderizar auditoria com cadeia de hash
- Renderizar perfil de usuário
- Construir cabeçalho e formatar export final

Conforme regras_e_padroes.md (SRP, lógica isolada).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from pyloto_corp.domain.audit import AuditEvent
from pyloto_corp.domain.conversations import ConversationMessage
from pyloto_corp.domain.profile import UserProfile

CPF_PATTERN = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def render_messages(
    messages: Iterable[ConversationMessage],
    tz: ZoneInfo,
    phone: str | None,
    include_pii: bool,
) -> list[str]:
    """Renderiza mensagens com timestamps localizados.

    Args:
        messages: Iterable de mensagens
        tz: Timezone para localização
        phone: Telefone (se include_pii e actor=USER)
        include_pii: Se incluir PII

    Returns:
        Lista de linhas formatadas
    """
    messages_list = list(messages)

    if not messages_list:
        placeholder_ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC).astimezone(tz)
        local_ts = placeholder_ts.strftime("%Y-%m-%d %H:%M:%S %z")
        return [f"[{local_ts}] NO_MESSAGES - N/A"]

    lines: list[str] = []
    for msg in messages_list:
        local_ts = msg.timestamp.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S %z")
        actor_label = msg.actor
        if include_pii and msg.actor == "USER" and phone:
            actor_label = f"USER({phone})"
        text = _mask_text(msg.text, include_pii)
        lines.append(f"[{local_ts}] {actor_label} - {text}")
    return lines


def _mask_text(text: str | None, include_pii: bool) -> str:
    _ = include_pii  # mantido para compatibilidade de assinatura
    if not text:
        return ""

    redacted = CPF_PATTERN.sub("[PII oculto]", text)
    redacted = EMAIL_PATTERN.sub("[PII oculto]", redacted)
    return redacted


def render_audit(events: Iterable[AuditEvent], tz: ZoneInfo) -> list[str]:
    """Renderiza auditoria com cadeia de hash (append-only).

    Args:
        events: Iterable de eventos de auditoria
        tz: Timezone para localização

    Returns:
        Lista de linhas formatadas com hashes
    """
    lines: list[str] = []
    for ev in events:
        local_ts = ev.timestamp.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S %z")
        chain_label = "CHAINED" if ev.prev_hash else "GENESIS"
        lines.append(
            f"[{local_ts}] {ev.action} {ev.actor} {ev.reason} "
            f"{ev.event_id} {ev.hash} prev={chain_label}"
        )
    return lines


def render_profile(profile: UserProfile | None, include_pii: bool) -> list[str]:
    """Renderiza dados de perfil.

    Args:
        profile: Perfil do usuário (pode ser None)
        include_pii: Se incluir PII

    Returns:
        Lista de linhas formatadas
    """
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

    lines.append("PII oculto")
    if profile.collected_fields:
        redacted_keys = ", ".join(sorted(profile.collected_fields.keys()))
        lines.append(f"Campos coletados: {redacted_keys}")
    else:
        lines.append("Nenhum campo coletado")
    return lines


def build_header(
    user_key: str,
    profile: UserProfile | None,
    phone_to_render: str | None,
    generated_at: datetime,
    tz: ZoneInfo,
) -> list[str]:
    """Constrói cabeçalho do export.

    Args:
        user_key: Chave de usuário
        profile: Perfil (pode ser None)
        phone_to_render: Telefone para incluir (se PII aprovado)
        generated_at: Timestamp de geração (UTC)
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


def format_export_text(
    header_lines: list[str],
    profile_lines: list[str],
    message_lines: list[str],
    audit_lines: list[str],
) -> str:
    """Formata seções do export em texto único.

    Args:
        header_lines: Cabeçalho
        profile_lines: Perfil
        message_lines: Mensagens
        audit_lines: Auditoria

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
