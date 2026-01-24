"""Testes para export de histórico de conversas."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pyloto_corp.domain.conversations import ConversationMessage
from pyloto_corp.domain.profile import UserProfile
from tests.unit.test_export_helpers import create_export_use_case


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
    assert (
        "2024-01-01 09:00:00" in result.export_text
        or "2024-01-01 12:00:00" in result.export_text
    )
    assert result.metadata["sha256_of_export"]
