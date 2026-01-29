"""Testes para mascaramento de histórico (mask_pii_in_history).

Valida que PII é removido antes de enviar para LLM.
"""

from __future__ import annotations

from pyloto_corp.ai.sanitizer import mask_pii_in_history


class TestMaskPIIInHistory:
    """Testes para mascaramento de histórico."""

    def test_mask_empty_history(self) -> None:
        """Histórico vazio deve retornar lista vazia."""
        result = mask_pii_in_history([])
        assert result == []

    def test_mask_cpf_in_history(self) -> None:
        """CPF em histórico deve ser mascarado."""
        history = [
            "Olá, meu CPF é 123.456.789-10",
            "Preciso de ajuda",
        ]
        result = mask_pii_in_history(history)
        assert "[CPF]" in result[0]
        assert "123.456.789-10" not in result[0]
        assert "Preciso de ajuda" in result[1]

    def test_mask_cnpj_in_history(self) -> None:
        """CNPJ em histórico deve ser mascarado."""
        history = [
            "Minha empresa: 12.345.678/0001-90",
        ]
        result = mask_pii_in_history(history)
        assert "[CNPJ]" in result[0]
        assert "12.345.678/0001-90" not in result[0]

    def test_mask_email_in_history(self) -> None:
        """E-mail em histórico deve ser mascarado."""
        history = [
            "Contato: john.doe@example.com",
        ]
        result = mask_pii_in_history(history)
        assert "[EMAIL]" in result[0]
        assert "john.doe@example.com" not in result[0]

    def test_mask_phone_in_history(self) -> None:
        """Telefone em histórico deve ser mascarado."""
        history = [
            "Ligue: (11) 98765-4321",
        ]
        result = mask_pii_in_history(history)
        assert "[PHONE]" in result[0]
        assert "98765-4321" not in result[0]

    def test_mask_multiple_pii_in_single_message(self) -> None:
        """Múltiplos PII em uma mensagem devem ser mascarados."""
        history = [
            "CPF: 123.456.789-10, e-mail: test@example.com, fone: (11) 98765-4321",
        ]
        result = mask_pii_in_history(history)
        single = result[0]
        assert "[CPF]" in single
        assert "[EMAIL]" in single
        assert "[PHONE]" in single
        # Nenhum dado original
        assert "123.456.789-10" not in single
        assert "test@example.com" not in single
        assert "98765-4321" not in single

    def test_truncate_history_to_last_5_messages(self) -> None:
        """Histórico com >5 mensagens deve truncar para últimas 5."""
        history = [f"Mensagem {i}" for i in range(10)]
        result = mask_pii_in_history(history)
        # Deve ter apenas 5 mensagens (últimas)
        assert len(result) == 5
        # Deve conter as últimas mensagens
        assert "Mensagem 9" in result[-1]
        assert "Mensagem 5" in result[0]
        # Não deve conter as primeiras
        assert not any("Mensagem 0" in msg for msg in result)
        assert not any("Mensagem 4" in msg for msg in result)

    def test_mask_and_truncate_together(self) -> None:
        """Mascaramento e truncagem devem trabalhar juntos."""
        history = [f"Msg {i}: CPF 123.456.789-10" for i in range(10)]
        result = mask_pii_in_history(history)
        # Deve ter 5 mensagens (truncado)
        assert len(result) == 5
        # Todas devem ter PII mascarado
        for msg in result:
            assert "[CPF]" in msg
            assert "123.456.789-10" not in msg

    def test_mask_deterministic(self) -> None:
        """Mascaramento deve ser determinístico (mesma entrada = mesma saída)."""
        history = [
            "CPF: 123.456.789-10",
        ]
        result1 = mask_pii_in_history(history)
        result2 = mask_pii_in_history(history)
        # Mesma entrada deve produzir mesma saída
        assert result1 == result2

    def test_mask_cpf_without_punctuation(self) -> None:
        """CPF sem pontuação também deve ser mascarado."""
        history = [
            "Meu CPF: 12345678910",
        ]
        result = mask_pii_in_history(history)
        assert "[CPF]" in result[0]
        assert "12345678910" not in result[0]

    def test_mask_phone_varied_formats(self) -> None:
        """Telefones em variados formatos devem ser mascarados."""
        history = [
            "Fone 1: +55 11 98765-4321",
            "Fone 2: (11) 98765-4321",
            "Fone 3: 11 98765-4321",
        ]
        result = mask_pii_in_history(history)
        # Todos devem ter telefone mascarado
        for msg in result:
            assert "[PHONE]" in msg
            # Nenhum padrão de telefone visível
            assert "98765-4321" not in msg
            assert "11 9" not in msg

    def test_mask_pix_keys_implicitly(self) -> None:
        """Chaves Pix (CPF/CNPJ/email/telefone) devem ser mascaradas como parte de PII."""
        # Pix por CPF
        history = ["Pix CPF: 123.456.789-10"]
        result = mask_pii_in_history(history)
        assert "[CPF]" in result[0]

        # Pix por e-mail
        history = ["Pix email: john@example.com"]
        result = mask_pii_in_history(history)
        assert "[EMAIL]" in result[0]

        # Pix por telefone
        history = ["Pix phone: (11) 98765-4321"]
        result = mask_pii_in_history(history)
        assert "[PHONE]" in result[0]

    def test_mask_preserves_structure(self) -> None:
        """Mascaramento deve preservar estrutura da mensagem."""
        history = [
            "Olá, meu CPF é 123.456.789-10 e meu e-mail é test@example.com.",
        ]
        result = mask_pii_in_history(history)
        msg = result[0]
        # Estrutura deve ser preservada (apenas PII substituído)
        assert msg.startswith("Olá")
        assert msg.endswith(".")
        assert "[CPF]" in msg
        assert "[EMAIL]" in msg
