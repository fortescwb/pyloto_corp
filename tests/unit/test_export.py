"""Testes para export de histórico de conversas."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from pyloto_corp.domain.conversations import ConversationMessage
from pyloto_corp.domain.profile import UserProfile
from tests.unit.test_export_helpers import (
    create_export_use_case,
    make_event,
)


def test_export_includes_phone_only_when_allowed():
    """Testa que PII é incluído/excluído conforme flag."""
    ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    messages = [
        ConversationMessage(
            provider="whatsapp",
            provider_message_id="m1",
            user_key="uk",
            tenant_id=None,
            direction="in",
            actor="USER",
            timestamp=ts,
            text="olá",
            correlation_id=None,
            intent=None,
            outcome=None,
            payload_ref=None,
        ),
        ConversationMessage(
            provider="whatsapp",
            provider_message_id="m2",
            user_key="uk",
            tenant_id=None,
            direction="out",
            actor="PYLOTO",
            timestamp=ts + timedelta(minutes=1),
            text="oi, tudo bem?",
            correlation_id=None,
            intent=None,
            outcome=None,
            payload_ref=None,
        ),
    ]
    profile = UserProfile(
        user_key="uk",
        phone_e164="+5511999999999",
        display_name="Teste",
        collected_fields={},
        created_at=ts,
        updated_at=ts,
    )

    use_case = create_export_use_case(messages, profile)

    # Sem PII: telefone não deve aparecer
    result_no_pii = use_case.execute(
        user_key="uk",
        include_pii=False,
        requester_actor="SYSTEM",
        reason="test",
    )
    assert "+5511" not in result_no_pii.export_text

    # Com PII: telefone deve aparecer
    result_with_pii = use_case.execute(
        user_key="uk",
        include_pii=True,
        requester_actor="SYSTEM",
        reason="test",
    )
    assert "+5511999999999" in result_with_pii.export_text


def test_export_contains_timestamps_and_sha():
    """Testa que export contém timestamps e hash SHA256."""
    ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    messages = [
        ConversationMessage(
            provider="whatsapp",
            provider_message_id="m1",
            user_key="uk",
            tenant_id=None,
            direction="in",
            actor="USER",
            timestamp=ts,
            text="a",
            correlation_id=None,
            intent=None,
            outcome=None,
            payload_ref=None,
        ),
    ]

    use_case = create_export_use_case(messages, None)

    result = use_case.execute(
        user_key="uk",
        include_pii=False,
        requester_actor="SYSTEM",
        reason="test",
    )

    # Validar que contém timestamp
    assert "2024-01-01" in result.export_text
    
    # Validar que SHA256 está nos metadados
    assert "sha256_of_export" in result.metadata
    export_hash = result.metadata["sha256_of_export"]
    expected_hash = hashlib.sha256(
        result.export_text.encode("utf-8")
    ).hexdigest()
    assert export_hash == expected_hash


def test_export_messages_render_with_timezone():
    """Testa que mensagens são renderizadas com timezone correto."""
    ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    messages = [
        ConversationMessage(
            provider="whatsapp",
            provider_message_id="m1",
            user_key="uk",
            tenant_id=None,
            direction="in",
            actor="USER",
            timestamp=ts,
            text="teste",
            correlation_id=None,
            intent=None,
            outcome=None,
            payload_ref=None,
        ),
    ]

    use_case = create_export_use_case(messages, None)
    result = use_case.execute(
        user_key="uk",
        include_pii=False,
        requester_actor="SYSTEM",
        reason="test",
        timezone="America/Sao_Paulo",
    )

    # São Paulo = UTC-3, então 12:00 UTC = 09:00 São Paulo
    assert "09:00" in result.export_text
    assert "USER" in result.export_text
    assert "teste" in result.export_text


def test_export_with_no_profile():
    """Testa export quando perfil do usuário não existe."""
    ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    messages = [
        ConversationMessage(
            provider="whatsapp",
            provider_message_id="m1",
            user_key="uk",
            tenant_id=None,
            direction="in",
            actor="USER",
            timestamp=ts,
            text="oi",
            correlation_id=None,
            intent=None,
            outcome=None,
            payload_ref=None,
        ),
    ]

    use_case = create_export_use_case(messages, profile=None)
    result = use_case.execute(
        user_key="uk",
        include_pii=False,
        requester_actor="SYSTEM",
        reason="test",
    )

    # Deve conter N/A ou mensagem similar
    assert "N/A" in result.export_text
    assert result.export_text is not None
    assert result.export_path is not None


def test_export_with_collected_fields():
    """Testa que campos coletados aparecem no export."""
    ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    messages = []
    profile = UserProfile(
        user_key="uk",
        phone_e164="+5511999999999",
        display_name="João Silva",
        collected_fields={
            "email": "joao@example.com",
            "city": "São Paulo",
        },
        created_at=ts,
        updated_at=ts,
    )

    use_case = create_export_use_case(messages, profile)
    result = use_case.execute(
        user_key="uk",
        include_pii=True,
        requester_actor="SYSTEM",
        reason="test",
    )

    assert "João Silva" in result.export_text
    assert "email" in result.export_text
    assert "joao@example.com" in result.export_text
    assert "city" in result.export_text
    assert "São Paulo" in result.export_text


def test_export_multiple_messages_render_order():
    """Testa que múltiplas mensagens são renderizadas em ordem."""
    ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    messages = [
        ConversationMessage(
            provider="whatsapp",
            provider_message_id="m1",
            user_key="uk",
            tenant_id=None,
            direction="in",
            actor="USER",
            timestamp=ts,
            text="primeira",
            correlation_id=None,
            intent=None,
            outcome=None,
            payload_ref=None,
        ),
        ConversationMessage(
            provider="whatsapp",
            provider_message_id="m2",
            user_key="uk",
            tenant_id=None,
            direction="out",
            actor="PYLOTO",
            timestamp=ts + timedelta(minutes=1),
            text="segunda",
            correlation_id=None,
            intent=None,
            outcome=None,
            payload_ref=None,
        ),
        ConversationMessage(
            provider="whatsapp",
            provider_message_id="m3",
            user_key="uk",
            tenant_id=None,
            direction="in",
            actor="USER",
            timestamp=ts + timedelta(minutes=2),
            text="terceira",
            correlation_id=None,
            intent=None,
            outcome=None,
            payload_ref=None,
        ),
    ]

    use_case = create_export_use_case(messages, None)
    result = use_case.execute(
        user_key="uk",
        include_pii=False,
        requester_actor="SYSTEM",
        reason="test",
    )

    # Validar que todas as mensagens estão presentes
    assert "primeira" in result.export_text
    assert "segunda" in result.export_text
    assert "terceira" in result.export_text
    
    # Validar ordem: primeira deve vir antes de segunda
    idx_primeira = result.export_text.index("primeira")
    idx_segunda = result.export_text.index("segunda")
    idx_terceira = result.export_text.index("terceira")
    assert idx_primeira < idx_segunda < idx_terceira


def test_export_metadata_includes_message_count():
    """Testa que metadados incluem contagem de mensagens."""
    ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    messages = [
        ConversationMessage(
            provider="whatsapp",
            provider_message_id=f"m{i}",
            user_key="uk",
            tenant_id=None,
            direction="in" if i % 2 == 0 else "out",
            actor="USER" if i % 2 == 0 else "PYLOTO",
            timestamp=ts + timedelta(minutes=i),
            text=f"msg{i}",
            correlation_id=None,
            intent=None,
            outcome=None,
            payload_ref=None,
        )
        for i in range(5)
    ]

    use_case = create_export_use_case(messages, None)
    result = use_case.execute(
        user_key="uk",
        include_pii=False,
        requester_actor="SYSTEM",
        reason="test",
    )

    assert result.metadata["message_count"] == 5


def test_export_user_key_derivation():
    """Testa que user_key é derivado de phone_e164 quando necessário."""
    ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    messages = []
    profile = UserProfile(
        user_key="uk_derived",
        phone_e164="+5511999999999",
        display_name="Teste",
        collected_fields={},
        created_at=ts,
        updated_at=ts,
    )

    use_case = create_export_use_case(messages, profile)
    
    # Invocar com phone_e164 em vez de user_key
    result = use_case.execute(
        phone_e164="+5511999999999",
        include_pii=False,
        requester_actor="SYSTEM",
        reason="test",
    )

    assert result.export_path is not None
    assert result.metadata is not None


def test_export_audit_event_recorded():
    """Testa que evento de export é registrado na auditoria."""
    ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    messages = []
    
    use_case = create_export_use_case(messages, None)
    result = use_case.execute(
        user_key="uk",
        include_pii=False,
        requester_actor="ADMIN",
        reason="LGPD_REQUEST",
    )

    # Validar que audit_tail_hash foi incluído nos metadados
    assert "audit_tail_hash" in result.metadata
    assert result.metadata["audit_tail_hash"] is not None


def test_export_result_structure():
    """Testa que ExportResult possui estrutura esperada."""
    ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    messages = [
        ConversationMessage(
            provider="whatsapp",
            provider_message_id="m1",
            user_key="uk",
            tenant_id=None,
            direction="in",
            actor="USER",
            timestamp=ts,
            text="x",
            correlation_id=None,
            intent=None,
            outcome=None,
            payload_ref=None,
        ),
    ]

    use_case = create_export_use_case(messages, None)
    result = use_case.execute(
        user_key="uk",
        include_pii=False,
        requester_actor="SYSTEM",
        reason="test",
    )

    # Validar que resultado possui os campos esperados
    assert hasattr(result, "export_text")
    assert hasattr(result, "export_path")
    assert hasattr(result, "metadata")
    assert isinstance(result.export_text, str)
    assert isinstance(result.export_path, str)
    assert isinstance(result.metadata, dict)


def test_export_requires_reason():
    """Testa que reason é obrigatório."""
    use_case = create_export_use_case([], None)
    
    # Deve falhar sem reason
    with pytest.raises(TypeError):
        use_case.execute(user_key="uk")  # reason não fornecido


def test_export_includes_header_sections():
    """Testa que export contém todas as seções esperadas."""
    ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
    messages = []

    use_case = create_export_use_case(messages, None)
    result = use_case.execute(
        user_key="uk",
        include_pii=False,
        requester_actor="SYSTEM",
        reason="test",
    )

    # Validar presença de seções
    assert "HISTÓRICO DE CONVERSA" in result.export_text
    assert "DADOS COLETADOS" in result.export_text
    assert "MENSAGENS" in result.export_text
    assert "AUDITORIA" in result.export_text

    assert (
        "2024-01-01 09:00:00" in result.export_text
        or "2024-01-01 12:00:00" in result.export_text
    )
    assert result.metadata["sha256_of_export"]
