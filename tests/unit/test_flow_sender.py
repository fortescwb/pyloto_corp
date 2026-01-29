"""Testes unitários para FlowSender — criptografia AES-GCM."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from typing import Any

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256

from pyloto_corp.adapters.whatsapp.flow_crypto import (
    AES_KEY_SIZE,
    IV_SIZE,
    FlowCryptoError,
)
from pyloto_corp.adapters.whatsapp.flow_sender import (
    DecryptedFlowData,
    FlowSender,
    create_flow_sender,
)

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def rsa_key_pair() -> tuple[str, str]:
    """Gera par de chaves RSA para testes."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


@pytest.fixture
def flow_sender(rsa_key_pair: tuple[str, str]) -> FlowSender:
    """Cria FlowSender com chaves de teste."""
    private_pem, _ = rsa_key_pair
    return FlowSender(
        private_key_pem=private_pem,
        flow_endpoint_secret="test_secret_123",
    )


@pytest.fixture
def sample_flow_data() -> dict[str, Any]:
    """Dados de exemplo para teste de Flow."""
    return {
        "flow_token": "test_token_abc123",
        "action": "navigate",
        "screen": "MAIN_MENU",
        "data": {"selected_option": "pricing"},
        "version": "1.0",
    }


# ============================================================
# Testes: Validação de Assinatura
# ============================================================


class TestValidateSignature:
    """Testes para validação de assinatura HMAC-SHA256."""

    def test_valid_signature_passes(self, flow_sender: FlowSender) -> None:
        """Assinatura válida deve passar."""
        payload = b'{"test": "data"}'
        secret = "test_secret_123"

        signature = "sha256=" + hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        assert flow_sender.validate_signature(payload, signature) is True

    def test_invalid_signature_fails(self, flow_sender: FlowSender) -> None:
        """Assinatura inválida deve falhar."""
        payload = b'{"test": "data"}'
        signature = "sha256=invalid_signature_here"

        assert flow_sender.validate_signature(payload, signature) is False

    def test_missing_prefix_fails(self, flow_sender: FlowSender) -> None:
        """Assinatura sem prefixo sha256= deve falhar."""
        payload = b'{"test": "data"}'
        signature = "some_signature_without_prefix"

        assert flow_sender.validate_signature(payload, signature) is False

    def test_tampered_payload_fails(self, flow_sender: FlowSender) -> None:
        """Payload adulterado deve falhar na validação."""
        original_payload = b'{"test": "data"}'
        secret = "test_secret_123"

        signature = "sha256=" + hmac.new(
            secret.encode(),
            original_payload,
            hashlib.sha256,
        ).hexdigest()

        tampered_payload = b'{"test": "hacked"}'

        assert flow_sender.validate_signature(tampered_payload, signature) is False


# ============================================================
# Testes: Decriptografia de Flow
# ============================================================


class TestDecryptRequest:
    """Testes para decriptografia de dados de Flow."""

    def test_decrypt_valid_data(
        self,
        rsa_key_pair: tuple[str, str],
        sample_flow_data: dict[str, Any],
    ) -> None:
        """Dados válidos devem ser descriptografados corretamente."""
        private_pem, public_pem = rsa_key_pair

        # Carregar chave pública para criptografar
        public_key = serialization.load_pem_public_key(
            public_pem.encode(),
            backend=default_backend(),
        )

        # Gerar chave AES e IV
        aes_key = os.urandom(AES_KEY_SIZE)
        iv = os.urandom(IV_SIZE)

        # Criptografar chave AES com RSA
        encrypted_aes_key = public_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=SHA256()),
                algorithm=SHA256(),
                label=None,
            ),
        )

        # Criptografar dados com AES-GCM
        aesgcm = AESGCM(aes_key)
        plaintext = json.dumps(sample_flow_data).encode("utf-8")
        ciphertext = aesgcm.encrypt(iv, plaintext, None)

        # Criar FlowSender e descriptografar
        flow_sender = FlowSender(
            private_key_pem=private_pem,
            flow_endpoint_secret="test_secret",
        )

        result = flow_sender.decrypt_request(
            encrypted_aes_key=base64.b64encode(encrypted_aes_key).decode(),
            encrypted_flow_data=base64.b64encode(ciphertext).decode(),
            initial_vector=base64.b64encode(iv).decode(),
        )

        assert isinstance(result, DecryptedFlowData)
        assert result.flow_token == sample_flow_data["flow_token"]
        assert result.action == sample_flow_data["action"]
        assert result.screen == sample_flow_data["screen"]
        assert result.data == sample_flow_data["data"]

    def test_decrypt_invalid_aes_key_fails(self, flow_sender: FlowSender) -> None:
        """Chave AES inválida deve falhar."""
        with pytest.raises(FlowCryptoError, match="decryption failed"):
            flow_sender.decrypt_request(
                encrypted_aes_key=base64.b64encode(b"invalid_key").decode(),
                encrypted_flow_data=base64.b64encode(b"some_data").decode(),
                initial_vector=base64.b64encode(b"some_iv_12b").decode(),
            )

    def test_decrypt_corrupted_data_fails(
        self,
        rsa_key_pair: tuple[str, str],
    ) -> None:
        """Dados corrompidos devem falhar."""
        private_pem, public_pem = rsa_key_pair

        public_key = serialization.load_pem_public_key(
            public_pem.encode(),
            backend=default_backend(),
        )

        aes_key = os.urandom(AES_KEY_SIZE)
        encrypted_aes_key = public_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=SHA256()),
                algorithm=SHA256(),
                label=None,
            ),
        )

        flow_sender = FlowSender(
            private_key_pem=private_pem,
            flow_endpoint_secret="test_secret",
        )

        with pytest.raises(FlowCryptoError, match="decryption failed"):
            flow_sender.decrypt_request(
                encrypted_aes_key=base64.b64encode(encrypted_aes_key).decode(),
                encrypted_flow_data=base64.b64encode(b"corrupted_data").decode(),
                initial_vector=base64.b64encode(os.urandom(IV_SIZE)).decode(),
            )


# ============================================================
# Testes: Criptografia de Resposta
# ============================================================


class TestEncryptResponse:
    """Testes para criptografia de resposta de Flow."""

    def test_encrypt_response_returns_all_fields(
        self,
        flow_sender: FlowSender,
    ) -> None:
        """Criptografia deve retornar todos os campos necessários."""
        response_data = {"screen": "NEXT", "data": {"result": "success"}}

        result = flow_sender.encrypt_response(response_data)

        assert "encrypted_response" in result
        assert "iv" in result
        assert "tag" in result

        # Verificar que são base64 válidos
        base64.b64decode(result["encrypted_response"])
        base64.b64decode(result["iv"])
        base64.b64decode(result["tag"])

    def test_encrypt_response_with_custom_key(
        self,
        flow_sender: FlowSender,
    ) -> None:
        """Criptografia com chave customizada deve funcionar."""
        response_data = {"action": "complete"}
        custom_key = os.urandom(AES_KEY_SIZE)

        result = flow_sender.encrypt_response(response_data, aes_key=custom_key)

        assert "encrypted_response" in result
        assert "iv" in result
        assert "tag" in result

    def test_encrypt_empty_response(self, flow_sender: FlowSender) -> None:
        """Resposta vazia deve ser criptografada."""
        result = flow_sender.encrypt_response({})

        assert "encrypted_response" in result
        assert len(result["encrypted_response"]) > 0


# ============================================================
# Testes: Health Check
# ============================================================


class TestHealthCheck:
    """Testes para health check."""

    def test_health_check_returns_healthy(self, flow_sender: FlowSender) -> None:
        """Health check deve retornar status healthy."""
        result = flow_sender.health_check()

        assert result["status"] == "healthy"
        assert "timestamp" in result
        assert "version" in result

    def test_health_check_timestamp_format(self, flow_sender: FlowSender) -> None:
        """Timestamp deve estar em formato ISO."""
        result = flow_sender.health_check()

        from datetime import datetime

        # Deve parsear sem erro
        datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))


# ============================================================
# Testes: Factory
# ============================================================


class TestCreateFlowSender:
    """Testes para factory function."""

    def test_create_flow_sender_success(
        self,
        rsa_key_pair: tuple[str, str],
    ) -> None:
        """Factory deve criar FlowSender válido."""
        private_pem, _ = rsa_key_pair

        sender = create_flow_sender(
            private_key_pem=private_pem,
            flow_endpoint_secret="secret",
        )

        assert isinstance(sender, FlowSender)

    def test_create_flow_sender_with_passphrase(self) -> None:
        """Factory deve suportar chave com senha."""
        # Gerar chave com senha
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )

        passphrase = "test_password"
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(
                passphrase.encode()
            ),
        ).decode("utf-8")

        sender = create_flow_sender(
            private_key_pem=private_pem,
            flow_endpoint_secret="secret",
            passphrase=passphrase,
        )

        assert isinstance(sender, FlowSender)

    def test_create_flow_sender_invalid_key_fails(self) -> None:
        """Factory com chave inválida deve falhar."""
        with pytest.raises(FlowCryptoError, match="Invalid private key"):
            create_flow_sender(
                private_key_pem="invalid_key",
                flow_endpoint_secret="secret",
            )


# ============================================================
# Testes: Edge Cases
# ============================================================


class TestFlowSenderEdgeCases:
    """Testes de casos de borda."""

    def test_empty_flow_token(self, flow_sender: FlowSender) -> None:
        """Criptografia com dados sem flow_token não deve falhar."""
        response = {"action": "error", "message": "No token"}
        result = flow_sender.encrypt_response(response)

        assert "encrypted_response" in result

    def test_large_payload(self, flow_sender: FlowSender) -> None:
        """Payload grande deve ser criptografado."""
        large_data = {"data": "x" * 10000}
        result = flow_sender.encrypt_response(large_data)

        assert len(result["encrypted_response"]) > 1000

    def test_unicode_in_payload(self, flow_sender: FlowSender) -> None:
        """Caracteres Unicode devem ser suportados."""
        unicode_data = {
            "message": "Olá, mundo! 🌍 日本語 العربية",
            "screen": "CONFIRMAÇÃO",
        }
        result = flow_sender.encrypt_response(unicode_data)

        assert "encrypted_response" in result
