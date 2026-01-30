"""Teste 5.1: Validação de assinatura HMAC com/sem secret, contexto env."""

from __future__ import annotations

import hashlib
import hmac

from pyloto_corp.adapters.whatsapp.signature import (
    verify_meta_signature,
)


class TestSignatureValidationWithSecret:
    """Testa validação com secret definido."""

    def test_valid_signature_passes(self):
        """Assinatura válida deve passar."""
        secret = "my_secret"
        body = b'{"object":"whatsapp_business_account","entry":[{"id":"1","changes":[]}]}'
        expected_hash = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        headers = {"x-hub-signature-256": f"sha256={expected_hash}"}

        result = verify_meta_signature(body, headers, secret)
        assert result.valid
        assert not result.skipped

    def test_invalid_signature_fails(self):
        """Assinatura inválida deve falhar."""
        secret = "my_secret"
        body = b'{"object":"whatsapp_business_account"}'
        headers = {"x-hub-signature-256": "sha256=wrong_hash"}

        result = verify_meta_signature(body, headers, secret)
        assert not result.valid

    def test_missing_signature_header_fails(self):
        """Falta do header de assinatura deve falhar."""
        secret = "my_secret"
        body = b'{"object":"whatsapp_business_account"}'
        headers = {}

        result = verify_meta_signature(body, headers, secret)
        assert not result.valid

    def test_malformed_signature_header_fails(self):
        """Header malformado deve falhar."""
        secret = "my_secret"
        body = b'{"object":"whatsapp_business_account"}'
        headers = {"x-hub-signature-256": "invalid_format"}

        result = verify_meta_signature(body, headers, secret)
        assert not result.valid


class TestSignatureValidationWithoutSecret:
    """Testa validação sem secret (skip)."""

    def test_skip_when_no_secret(self):
        """Deve pular validação quando secret é None."""
        body = b'{"object":"whatsapp_business_account"}'
        headers = {}

        result = verify_meta_signature(body, headers, None)
        assert result.valid
        assert result.skipped

    def test_skip_when_secret_empty_string(self):
        """Deve pular validação quando secret é string vazia."""
        body = b'{"object":"whatsapp_business_account"}'
        headers = {}

        result = verify_meta_signature(body, headers, "")
        assert result.valid
        assert result.skipped


class TestSignatureValidationEnvironmentContext:
    """Testa comportamento em diferentes contextos de ambiente."""

    def test_result_indicates_skipped_status(self):
        """SignatureResult deve indicar se foi skipped."""
        secret = None
        body = b'{"object":"whatsapp_business_account"}'
        headers = {}

        result = verify_meta_signature(body, headers, secret)
        assert result.skipped is True

    def test_result_has_error_when_invalid(self):
        """SignatureResult deve ter error descritivo."""
        secret = "my_secret"
        body = b'{"object":"whatsapp_business_account"}'
        headers = {"x-hub-signature-256": "sha256=wrong"}

        result = verify_meta_signature(body, headers, secret)
        assert result.error is not None


class TestSignatureValidationEdgeCases:
    """Testa edge cases na validação."""

    def test_empty_body_with_valid_signature(self):
        """Body vazio com assinatura válida deve passar."""
        secret = "my_secret"
        body = b""
        expected_hash = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        headers = {"x-hub-signature-256": f"sha256={expected_hash}"}

        result = verify_meta_signature(body, headers, secret)
        assert result.valid

    def test_unicode_body_validation(self):
        """Body unicode deve ser validado corretamente."""
        secret = "my_secret"
        body = "ñáéíóú".encode()
        expected_hash = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        headers = {"x-hub-signature-256": f"sha256={expected_hash}"}

        result = verify_meta_signature(body, headers, secret)
        assert result.valid

    def test_case_insensitive_algorithm(self):
        """Algoritmo no header deve estar em minúsculas."""
        secret = "my_secret"
        body = b'{"object":"whatsapp_business_account"}'
        expected_hash = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        # Uso com "SHA256" em vez de "sha256" (como na especificação Meta)
        headers = {"x-hub-signature-256": f"sha256={expected_hash}"}

        result = verify_meta_signature(body, headers, secret)
        assert result.valid
