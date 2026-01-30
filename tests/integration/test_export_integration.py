"""Testes E2E de integração entre export e persistência em Firestore."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pyloto_corp.domain.conversations import ConversationMessage
from pyloto_corp.domain.profile import UserProfile

from ..unit.test_export_helpers import (
    create_export_use_case,
)


class TestExportIntegration:
    """Testes de integração: export + armazenamento de conversas."""

    def test_export_persists_result_to_exporter(self):
        """Testa que export persiste resultado via HistoryExporter."""
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
        result = use_case.execute(
            user_key="uk",
            include_pii=False,
            requester_actor="SYSTEM",
            reason="test",
        )

        # Validar que caminho foi gerado
        assert result.export_path is not None
        assert "uk" in result.export_path

    def test_export_flow_with_multiple_messages(self):
        """Testa fluxo de export com múltiplas mensagens."""
        ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
        messages = []

        # Adicionar 10 mensagens alternando direção
        for i in range(10):
            direction = "in" if i % 2 == 0 else "out"
            actor = "USER" if i % 2 == 0 else "PYLOTO"
            messages.append(
                ConversationMessage(
                    provider="whatsapp",
                    provider_message_id=f"m{i}",
                    user_key="uk",
                    tenant_id=None,
                    direction=direction,
                    actor=actor,
                    timestamp=ts + timedelta(minutes=i),
                    text=f"mensagem {i}",
                    correlation_id=None,
                    intent=None,
                    outcome=None,
                    payload_ref=None,
                )
            )

        use_case = create_export_use_case(messages, None)
        result = use_case.execute(
            user_key="uk",
            include_pii=False,
            requester_actor="SYSTEM",
            reason="test",
        )

        # Validar que todas as mensagens aparecem no export
        for i in range(10):
            assert f"mensagem {i}" in result.export_text

        # Validar contagem de mensagens nos metadados
        assert result.metadata["message_count"] == 10

    def test_export_preserves_message_order(self):
        """Testa que ordem de mensagens é preservada no export."""
        ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
        messages = []

        for i in range(5):
            messages.append(
                ConversationMessage(
                    provider="whatsapp",
                    provider_message_id=f"m{i}",
                    user_key="uk",
                    tenant_id=None,
                    direction="in",
                    actor="USER",
                    timestamp=ts + timedelta(seconds=i * 10),
                    text=f"msg_{i:02d}",
                    correlation_id=None,
                    intent=None,
                    outcome=None,
                    payload_ref=None,
                )
            )

        use_case = create_export_use_case(messages, None)
        result = use_case.execute(
            user_key="uk",
            include_pii=False,
            requester_actor="SYSTEM",
            reason="test",
        )

        # Validar ordem
        positions = [result.export_text.index(f"msg_{i:02d}") for i in range(5)]
        assert positions == sorted(positions)

    def test_export_with_tenant_isolation(self):
        """Testa que exports respeitam tenant_id."""
        ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

        messages_tenant_a = [
            ConversationMessage(
                provider="whatsapp",
                provider_message_id="m1",
                user_key="uk_a",
                tenant_id="tenant_a",
                direction="in",
                actor="USER",
                timestamp=ts,
                text="tenant_a_msg",
                correlation_id=None,
                intent=None,
                outcome=None,
                payload_ref=None,
            ),
        ]

        messages_tenant_b = [
            ConversationMessage(
                provider="whatsapp",
                provider_message_id="m2",
                user_key="uk_b",
                tenant_id="tenant_b",
                direction="in",
                actor="USER",
                timestamp=ts,
                text="tenant_b_msg",
                correlation_id=None,
                intent=None,
                outcome=None,
                payload_ref=None,
            ),
        ]

        # Export para tenant A
        use_case_a = create_export_use_case(messages_tenant_a, None)
        result_a = use_case_a.execute(
            user_key="uk_a",
            include_pii=False,
            requester_actor="SYSTEM",
            reason="test",
            tenant_id="tenant_a",
        )

        # Export para tenant B
        use_case_b = create_export_use_case(messages_tenant_b, None)
        result_b = use_case_b.execute(
            user_key="uk_b",
            include_pii=False,
            requester_actor="SYSTEM",
            reason="test",
            tenant_id="tenant_b",
        )

        # Validar isolamento
        assert "tenant_a_msg" in result_a.export_text
        assert "tenant_a_msg" not in result_b.export_text
        assert "tenant_b_msg" in result_b.export_text
        assert "tenant_b_msg" not in result_a.export_text

    def test_export_audit_trail_integration(self):
        """Testa que auditoria é integrada com export."""
        datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
        messages = []

        use_case = create_export_use_case(messages, None)
        result = use_case.execute(
            user_key="uk",
            include_pii=False,
            requester_actor="ADMIN",
            reason="LGPD_REQUEST",
        )

        # Validar que evento de auditoria foi registrado
        assert "audit_tail_hash" in result.metadata
        assert result.metadata["audit_tail_hash"] is not None

        # Validar que metadados contêm informações de auditoria
        assert "generated_at" in result.metadata
        assert "export_path" in result.metadata

    def test_export_handles_pii_correctly_end_to_end(self):
        """Testa fluxo completo de PII masking."""
        ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

        profile = UserProfile(
            user_key="uk",
            phone_e164="+5511999999999",
            display_name="João Silva",
            collected_fields={
                "email": "joao@example.com",
                "ssn": "123.456.789-00",
            },
            created_at=ts,
            updated_at=ts,
        )

        messages = [
            ConversationMessage(
                provider="whatsapp",
                provider_message_id="m1",
                user_key="uk",
                tenant_id=None,
                direction="in",
                actor="USER",
                timestamp=ts,
                text="Meu CPF é 123.456.789-00",
                correlation_id=None,
                intent=None,
                outcome=None,
                payload_ref=None,
            ),
        ]

        use_case = create_export_use_case(messages, profile)

        # Export sem PII
        result_no_pii = use_case.execute(
            user_key="uk",
            include_pii=False,
            requester_actor="SYSTEM",
            reason="test",
        )

        # Email e SSN não devem aparecer
        assert "joao@example.com" not in result_no_pii.export_text
        assert "123.456.789-00" not in result_no_pii.export_text
        assert "+5511" not in result_no_pii.export_text

        # Export com PII
        result_with_pii = use_case.execute(
            user_key="uk",
            include_pii=True,
            requester_actor="ADMIN",
            reason="test",
        )

        # Email e telefone devem aparecer
        assert "joao@example.com" in result_with_pii.export_text
        assert "+5511999999999" in result_with_pii.export_text

    def test_export_result_immutability(self):
        """Testa que resultado de export é estável."""
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
                text="msg",
                correlation_id=None,
                intent=None,
                outcome=None,
                payload_ref=None,
            ),
        ]

        use_case = create_export_use_case(messages, None)
        result1 = use_case.execute(
            user_key="uk",
            include_pii=False,
            requester_actor="SYSTEM",
            reason="test",
        )

        # Export novamente com mesmos dados
        result2 = use_case.execute(
            user_key="uk",
            include_pii=False,
            requester_actor="SYSTEM",
            reason="test",
        )

        # Conteúdo de export deve ser similar (timestamps podem variar)
        assert len(result1.export_text) == len(result2.export_text)
        assert result1.metadata["message_count"] == result2.metadata["message_count"]

    def test_export_error_handling_with_missing_data(self):
        """Testa tratamento de erro quando dados estão ausentes."""
        use_case = create_export_use_case([], None)

        # Export sem erros mesmo com dados vazios
        result = use_case.execute(
            user_key="uk",
            include_pii=False,
            requester_actor="SYSTEM",
            reason="test",
        )

        assert result.export_text is not None
        assert result.export_path is not None
        assert result.metadata["message_count"] == 0

    def test_export_handles_special_characters(self):
        """Testa que export lida corretamente com caracteres especiais."""
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
                text="Olá! Como vai? ñ à é ü 中文 😀",
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

        # Validar que caracteres especiais foram preservados
        assert "ñ" in result.export_text
        assert "é" in result.export_text
        assert "😀" in result.export_text

    def test_export_multiple_users_isolation(self):
        """Testa que exports de usuários diferentes são isolados."""
        ts = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

        messages_uk1 = [
            ConversationMessage(
                provider="whatsapp",
                provider_message_id="m1",
                user_key="uk1",
                tenant_id=None,
                direction="in",
                actor="USER",
                timestamp=ts,
                text="mensagem_user1",
                correlation_id=None,
                intent=None,
                outcome=None,
                payload_ref=None,
            ),
        ]

        messages_uk2 = [
            ConversationMessage(
                provider="whatsapp",
                provider_message_id="m2",
                user_key="uk2",
                tenant_id=None,
                direction="in",
                actor="USER",
                timestamp=ts,
                text="mensagem_user2",
                correlation_id=None,
                intent=None,
                outcome=None,
                payload_ref=None,
            ),
        ]

        use_case1 = create_export_use_case(messages_uk1, None)
        use_case2 = create_export_use_case(messages_uk2, None)

        result1 = use_case1.execute(
            user_key="uk1",
            include_pii=False,
            requester_actor="SYSTEM",
            reason="test",
        )

        result2 = use_case2.execute(
            user_key="uk2",
            include_pii=False,
            requester_actor="SYSTEM",
            reason="test",
        )

        # Validar isolamento
        assert "mensagem_user1" in result1.export_text
        assert "mensagem_user1" not in result2.export_text
        assert "mensagem_user2" in result2.export_text
        assert "mensagem_user2" not in result1.export_text
