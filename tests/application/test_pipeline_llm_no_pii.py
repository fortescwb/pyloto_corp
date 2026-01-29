"""Testes que garantem que nenhum PII chega ao OpenAI.

Valida que mask_pii_in_history é aplicado antes de enviar para LLM.
"""

from __future__ import annotations


class TestPipelineLLMNoPII:
    """Testes que garantem que PII nunca chega ao OpenAI."""

    def test_pipeline_masks_history_before_llm_call(self) -> None:
        """Histórico com PII deve ser mascarado antes de chegar ao OpenAI."""
        from pyloto_corp.ai.sanitizer import mask_pii_in_history

        history = [
            "Meu CPF é 123.456.789-10",
            "E-mail: test@example.com",
            "Fone: (11) 98765-4321",
        ]

        masked = mask_pii_in_history(history)

        # Nenhum PII deve estar visível
        assert "123.456.789-10" not in str(masked)
        assert "test@example.com" not in str(masked)
        assert "98765-4321" not in str(masked)

        # Máscaras devem estar presentes
        assert "[CPF]" in str(masked)
        assert "[EMAIL]" in str(masked)
        assert "[PHONE]" in str(masked)

    def test_mask_truncates_to_5_messages_max(self) -> None:
        """Histórico deve ser truncado para últimas 5 mensagens."""
        from pyloto_corp.ai.sanitizer import mask_pii_in_history

        history = [f"Msg {i}: CPF 123.456.789-10" for i in range(10)]
        masked = mask_pii_in_history(history)

        # Deve ter apenas 5 mensagens
        assert len(masked) == 5
        # Deve incluir última mensagem
        assert "Msg 9" in masked[-1]
        # Não deve incluir primeira
        assert not any("Msg 0" in msg for msg in masked)

    def test_mask_deterministic_across_calls(self) -> None:
        """Mascaramento deve ser determinístico."""
        from pyloto_corp.ai.sanitizer import mask_pii_in_history

        history = ["CPF: 123.456.789-10", "Phone: (11) 98765-4321"]

        result1 = mask_pii_in_history(history)
        result2 = mask_pii_in_history(history)

        # Deve produzir resultado idêntico
        assert result1 == result2

    def test_empty_history_returns_empty(self) -> None:
        """Histórico vazio deve retornar lista vazia."""
        from pyloto_corp.ai.sanitizer import mask_pii_in_history

        masked = mask_pii_in_history([])
        assert masked == []

    def test_mask_preserves_message_structure(self) -> None:
        """Mascaramento deve preservar estrutura das mensagens."""
        from pyloto_corp.ai.sanitizer import mask_pii_in_history

        history = ["Olá, meu CPF é 123.456.789-10 e e-mail é test@example.com."]
        masked = mask_pii_in_history(history)

        msg = masked[0]
        # Estrutura preservada
        assert msg.startswith("Olá")
        assert msg.endswith(".")
        # PII mascarado
        assert "[CPF]" in msg
        assert "[EMAIL]" in msg
        # Sem dados sensíveis em claro
        assert "123.456.789-10" not in msg
        assert "test@example.com" not in msg

    def test_mask_applied_in_pipeline_integration(self) -> None:
        """Verificar que mask_pii_in_history é importado e aplicado no pipeline."""
        import inspect

        # Verificar que mask_pii_in_history é importado em pipeline_v2
        from pyloto_corp.application import pipeline_v2

        source = inspect.getsource(pipeline_v2)
        assert "mask_pii_in_history" in source
        # Verificar que está sendo usado em LLM#1
        assert "mask_pii_in_history(session.message_history)" in source

    def test_llm1_masked_history_call(self) -> None:
        """Simular chamada LLM#1 com histórico mascarado."""
        from pyloto_corp.ai.sanitizer import mask_pii_in_history

        # Simular histórico com PII
        session_history = [
            "Olá, meu CPF é 123.456.789-10",
            "E-mail para contato: john@example.com",
            "Telefone: (11) 98765-4321",
            "Preciso de ajuda",
            "Obrigado",
        ]

        # Aplicar mascaramento como faria o pipeline
        masked_history = mask_pii_in_history(session_history)

        # Validações
        assert len(masked_history) == 5  # Truncado para últimas 5
        assert all(
            "[CPF]" in msg or "[EMAIL]" in msg or "[PHONE]" in msg
            for msg in masked_history[:3]
        )
        # Nenhum PII em claro
        for msg in masked_history:
            assert "123.456.789-10" not in msg
            assert "@example.com" not in msg
            assert "98765-4321" not in msg

    def test_cpf_variants_masked(self) -> None:
        """Testar variantes de CPF sendo mascaradas."""
        from pyloto_corp.ai.sanitizer import sanitize_response_content

        # CPF com pontuação
        result1 = sanitize_response_content("CPF: 123.456.789-10")
        assert "[CPF]" in result1

        # CPF sem pontuação
        result2 = sanitize_response_content("CPF: 12345678910")
        assert "[CPF]" in result2

    def test_phone_variants_masked(self) -> None:
        """Testar variantes de telefone sendo mascaradas."""
        from pyloto_corp.ai.sanitizer import sanitize_response_content

        variants = [
            "Fone: +55 11 98765-4321",
            "Fone: (11) 98765-4321",
            "Fone: 11 98765-4321",
        ]

        for variant in variants:
            result = sanitize_response_content(variant)
            assert "[PHONE]" in result
            assert "98765-4321" not in result
