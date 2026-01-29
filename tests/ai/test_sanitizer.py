"""Testes para módulo sanitizer (mascaramento de PII)."""

from __future__ import annotations

from pyloto_corp.ai.sanitizer import (
    _get_sanitize_fingerprint,
    mask_pii_in_history,
    sanitize_response_content,
)


class TestSanitizeResponseContent:
    """Testes para sanitize_response_content()."""

    def test_sanitize_cpf_formatted(self):
        """Deve mascarar CPF formatado (123.456.789-10)."""
        text = "Meu CPF é 123.456.789-10"
        result = sanitize_response_content(text)
        assert "[CPF]" in result
        assert "123.456.789-10" not in result

    def test_sanitize_cpf_unformatted(self):
        """Deve mascarar CPF sem formatação (12345678910)."""
        text = "CPF: 12345678910"
        result = sanitize_response_content(text)
        assert "[CPF]" in result
        assert "12345678910" not in result

    def test_sanitize_cnpj_formatted(self):
        """Deve mascarar CNPJ formatado (12.345.678/0001-90)."""
        text = "CNPJ: 12.345.678/0001-90"
        result = sanitize_response_content(text)
        assert "[CNPJ]" in result
        assert "12.345.678/0001-90" not in result

    def test_sanitize_email(self):
        """Deve mascarar e-mail."""
        text = "Contate john.doe@example.com"
        result = sanitize_response_content(text)
        assert "[EMAIL]" in result
        assert "john.doe@example.com" not in result

    def test_sanitize_phone(self):
        """Deve mascarar telefone formatado."""
        text = "Tel: (11) 98765-4321"
        result = sanitize_response_content(text)
        assert "[PHONE]" in result
        assert "98765-4321" not in result

    def test_sanitize_multiple_pii(self):
        """Deve mascarar múltiplos PII."""
        text = "CPF 123.456.789-10, john@example.com, (11) 98765-4321"
        result = sanitize_response_content(text)
        assert "[CPF]" in result
        assert "[EMAIL]" in result
        assert "[PHONE]" in result

    def test_sanitize_empty_string(self):
        """Deve retornar string vazia sem erro."""
        result = sanitize_response_content("")
        assert result == ""

    def test_sanitize_no_pii(self):
        """Deve retornar texto sem PII inalterado."""
        text = "Olá, como posso ajudá-lo?"
        result = sanitize_response_content(text)
        assert result == text

    def test_sanitize_deterministic(self):
        """Deve ser determinístico."""
        text = "CPF 123.456.789-10"
        result1 = sanitize_response_content(text)
        result2 = sanitize_response_content(text)
        assert result1 == result2

    def test_sanitize_idempotent(self):
        """Aplicar sanitização múltiplas vezes deve ser idempotente."""
        text = "CPF 123.456.789-10"
        result1 = sanitize_response_content(text)
        result2 = sanitize_response_content(result1)
        assert result1 == result2


class TestMaskPiiInHistory:
    """Testes para mask_pii_in_history()."""

    def test_mask_history_with_pii(self):
        """Deve mascarar histórico contendo PII."""
        messages = ["Meu CPF é 123.456.789-10", "john@example.com", "(11) 98765-4321"]
        result = mask_pii_in_history(messages)
        assert "123.456.789-10" not in result[0]

    def test_mask_history_truncate(self):
        """Deve truncar para últimas 5 mensagens."""
        messages = [f"Msg {i}" for i in range(10)]
        result = mask_pii_in_history(messages)
        assert len(result) == 5

    def test_mask_history_empty(self):
        """Deve retornar lista vazia para entrada vazia."""
        result = mask_pii_in_history([])
        assert result == []


class TestSanitizeFingerprint:
    """Testes para determinismo."""

    def test_fingerprint_deterministic(self):
        """Fingerprint deve ser determinístico."""
        text = "CPF 123.456.789-10"
        fp1 = _get_sanitize_fingerprint(text)
        fp2 = _get_sanitize_fingerprint(text)
        assert fp1 == fp2
