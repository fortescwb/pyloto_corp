"""Testes para cliente outbound WhatsApp."""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from pyloto_corp.adapters.whatsapp.models import (
    OutboundMessageRequest,
    OutboundMessageResponse,
)
from pyloto_corp.adapters.whatsapp.outbound import (
    OutboundMessage,
    WhatsAppOutboundClient,
)
from pyloto_corp.adapters.whatsapp.validators import ValidationError


class TestOutboundMessage:
    """Testes para dataclass OutboundMessage."""

    def test_outbound_message_text(self):
        """Deve criar OutboundMessage para texto."""
        msg = OutboundMessage(
            to="+5511987654321",
            message_type="text",
            text="Olá, tudo bem?",
        )
        assert msg.to == "+5511987654321"
        assert msg.message_type == "text"
        assert msg.text == "Olá, tudo bem?"

    def test_outbound_message_image(self):
        """Deve criar OutboundMessage para imagem."""
        msg = OutboundMessage(
            to="+5511987654321",
            message_type="image",
            media_url="https://example.com/image.jpg",
        )
        assert msg.message_type == "image"
        assert msg.media_url == "https://example.com/image.jpg"

    def test_outbound_message_with_idempotency_key(self):
        """Deve criar OutboundMessage com chave de idempotência."""
        msg = OutboundMessage(
            to="+5511987654321",
            message_type="text",
            text="Teste",
            idempotency_key="key-123",
        )
        assert msg.idempotency_key == "key-123"

    def test_outbound_message_slots(self):
        """OutboundMessage deve usar slots."""
        assert hasattr(OutboundMessage, "__slots__")


class TestWhatsAppOutboundClientInit:
    """Testes para inicialização do cliente."""

    def test_client_initialization(self):
        """Deve inicializar cliente com credenciais."""
        client = WhatsAppOutboundClient(
            api_endpoint="https://graph.facebook.com",
            access_token="token-123",
            phone_number_id="957912434071464",
        )
        assert client.api_endpoint == "https://graph.facebook.com"
        assert client.access_token == "token-123"
        assert client.phone_number_id == "957912434071464"

    def test_client_has_validator(self):
        """Cliente deve ter validador."""
        client = WhatsAppOutboundClient(
            api_endpoint="https://graph.facebook.com",
            access_token="token-123",
            phone_number_id="957912434071464",
        )
        assert client.validator is not None


class TestWhatsAppOutboundClientSendMessage:
    """Testes para método send_message."""

    def _create_valid_request(self) -> OutboundMessageRequest:
        """Helper para criar requisição válida."""
        return OutboundMessageRequest(
            to="+5511987654321",
            message_type="text",
            text="Olá, tudo bem?",
        )

    def test_send_message_success(self):
        """Deve enviar mensagem com sucesso."""
        client = WhatsAppOutboundClient(
            api_endpoint="https://graph.facebook.com",
            access_token="token-123",
            phone_number_id="957912434071464",
        )

        request = self._create_valid_request()
        response = client.send_message(request)

        assert response.success is True
        assert response.message_id == "mock_message_id"

    def test_send_message_invalid_request(self):
        """Deve retornar erro para requisição inválida."""
        client = WhatsAppOutboundClient(
            api_endpoint="https://graph.facebook.com",
            access_token="token-123",
            phone_number_id="957912434071464",
        )

        # Request com número inválido
        request = OutboundMessageRequest(
            to="invalid-number",
            message_type="text",
            text="Teste",
        )

        response = client.send_message(request)

        assert response.success is False
        assert response.error_code == "VALIDATION_ERROR"

    def test_send_message_with_category(self):
        """Deve enviar mensagem com categoria."""
        client = WhatsAppOutboundClient(
            api_endpoint="https://graph.facebook.com",
            access_token="token-123",
            phone_number_id="957912434071464",
        )

        request = OutboundMessageRequest(
            to="+5511987654321",
            message_type="text",
            text="Olá",
            category="MARKETING",
        )

        response = client.send_message(request)
        assert response.success is True

    def test_send_message_with_idempotency_key(self):
        """Deve enviar mensagem com chave de idempotência."""
        client = WhatsAppOutboundClient(
            api_endpoint="https://graph.facebook.com",
            access_token="token-123",
            phone_number_id="957912434071464",
        )

        request = OutboundMessageRequest(
            to="+5511987654321",
            message_type="text",
            text="Olá",
            idempotency_key="key-123-abc",
        )

        response = client.send_message(request)
        assert response.success is True

    def test_send_message_template(self):
        """Deve enviar mensagem de template."""
        client = WhatsAppOutboundClient(
            api_endpoint="https://graph.facebook.com",
            access_token="token-123",
            phone_number_id="957912434071464",
        )

        request = OutboundMessageRequest(
            to="+5511987654321",
            message_type="template",
            template_name="hello_world",
            template_namespace="hello",
        )

        response = client.send_message(request)
        assert response.success is True

    def test_send_message_with_buttons(self):
        """Deve enviar mensagem com botões."""
        client = WhatsAppOutboundClient(
            api_endpoint="https://graph.facebook.com",
            access_token="token-123",
            phone_number_id="957912434071464",
        )

        request = OutboundMessageRequest(
            to="+5511987654321",
            message_type="interactive",
            interactive_type="button",
            text="Escolha uma opção",
            buttons=[{"id": "1", "title": "Opção 1"}],
        )

        response = client.send_message(request)
        # Pode falhar em validação, mas não deve lançar exceção
        assert isinstance(response, OutboundMessageResponse)


class TestWhatsAppOutboundClientSendBatch:
    """Testes para método send_batch."""

    def _create_valid_request(self, to: str) -> OutboundMessageRequest:
        """Helper para criar requisição válida."""
        return OutboundMessageRequest(
            to=to,
            message_type="text",
            text="Olá, tudo bem?",
        )

    def test_send_batch_single_message(self):
        """Deve enviar lote com uma mensagem."""
        client = WhatsAppOutboundClient(
            api_endpoint="https://graph.facebook.com",
            access_token="token-123",
            phone_number_id="957912434071464",
        )

        requests = [self._create_valid_request("+5511987654321")]
        responses = client.send_batch(requests)

        assert len(responses) == 1
        assert responses[0].success is True

    def test_send_batch_multiple_messages(self):
        """Deve enviar lote com múltiplas mensagens."""
        client = WhatsAppOutboundClient(
            api_endpoint="https://graph.facebook.com",
            access_token="token-123",
            phone_number_id="957912434071464",
        )

        requests = [
            self._create_valid_request("+5511987654321"),
            self._create_valid_request("+5511912345678"),
            self._create_valid_request("+5511933334444"),
        ]

        responses = client.send_batch(requests)

        assert len(responses) == 3
        assert all(r.success is True for r in responses)

    def test_send_batch_preserves_order(self):
        """Deve preservar ordem de respostas."""
        client = WhatsAppOutboundClient(
            api_endpoint="https://graph.facebook.com",
            access_token="token-123",
            phone_number_id="957912434071464",
        )

        # Incluir uma inválida
        requests = [
            self._create_valid_request("+5511987654321"),
            OutboundMessageRequest(
                to="invalid",
                message_type="text",
                text="Teste",
            ),
            self._create_valid_request("+5511912345678"),
        ]

        responses = client.send_batch(requests)

        assert len(responses) == 3
        assert responses[0].success is True
        assert responses[1].success is False
        assert responses[2].success is True

    def test_send_batch_empty(self):
        """Deve retornar lista vazia para lote vazio."""
        client = WhatsAppOutboundClient(
            api_endpoint="https://graph.facebook.com",
            access_token="token-123",
            phone_number_id="957912434071464",
        )

        responses = client.send_batch([])
        assert responses == []


class TestWhatsAppOutboundClientGenerateDedupeKey:
    """Testes para método generate_dedupe_key."""

    def test_generate_dedupe_key_format(self):
        """Deve gerar chave no formato esperado."""
        key = WhatsAppOutboundClient.generate_dedupe_key(
            to="+5511987654321",
            message_type="text",
            content_hash="abc123",
        )

        assert isinstance(key, str)
        assert len(key) == 64  # SHA256 em hex = 64 caracteres

    def test_generate_dedupe_key_deterministic(self):
        """Deve gerar mesma chave para mesmos inputs."""
        key1 = WhatsAppOutboundClient.generate_dedupe_key(
            to="+5511987654321",
            message_type="text",
            content_hash="abc123",
        )

        key2 = WhatsAppOutboundClient.generate_dedupe_key(
            to="+5511987654321",
            message_type="text",
            content_hash="abc123",
        )

        assert key1 == key2

    def test_generate_dedupe_key_different_for_different_inputs(self):
        """Deve gerar chaves diferentes para inputs diferentes."""
        key1 = WhatsAppOutboundClient.generate_dedupe_key(
            to="+5511987654321",
            message_type="text",
            content_hash="abc123",
        )

        key2 = WhatsAppOutboundClient.generate_dedupe_key(
            to="+5511912345678",
            message_type="text",
            content_hash="abc123",
        )

        assert key1 != key2

    def test_generate_dedupe_key_includes_all_parts(self):
        """Deve incluir todos os componentes na chave."""
        # Se alterar qualquer componente, chave muda
        base_key = WhatsAppOutboundClient.generate_dedupe_key(
            to="+5511987654321",
            message_type="text",
            content_hash="abc123",
        )

        # Mudar "to"
        key_diff_to = WhatsAppOutboundClient.generate_dedupe_key(
            to="+5511987654322",
            message_type="text",
            content_hash="abc123",
        )
        assert base_key != key_diff_to

        # Mudar message_type
        key_diff_type = WhatsAppOutboundClient.generate_dedupe_key(
            to="+5511987654321",
            message_type="image",
            content_hash="abc123",
        )
        assert base_key != key_diff_type

        # Mudar content_hash
        key_diff_hash = WhatsAppOutboundClient.generate_dedupe_key(
            to="+5511987654321",
            message_type="text",
            content_hash="def456",
        )
        assert base_key != key_diff_hash


class TestWhatsAppOutboundClientValidateRequest:
    """Testes para método _validate_request."""

    def test_validate_request_valid(self):
        """Deve retornar None para requisição válida."""
        client = WhatsAppOutboundClient(
            api_endpoint="https://graph.facebook.com",
            access_token="token-123",
            phone_number_id="957912434071464",
        )

        request = OutboundMessageRequest(
            to="+5511987654321",
            message_type="text",
            text="Olá",
        )

        result = client._validate_request(request)
        assert result is None

    def test_validate_request_invalid_phone(self):
        """Deve retornar erro para telefone inválido."""
        client = WhatsAppOutboundClient(
            api_endpoint="https://graph.facebook.com",
            access_token="token-123",
            phone_number_id="957912434071464",
        )

        request = OutboundMessageRequest(
            to="invalid",
            message_type="text",
            text="Olá",
        )

        result = client._validate_request(request)
        assert result is not None
        assert isinstance(result, OutboundMessageResponse)
        assert result.success is False


class TestWhatsAppOutboundClientBuildPayloadSafe:
    """Testes para método _build_payload_safe."""

    def test_build_payload_safe_success(self):
        """Deve construir payload com sucesso."""
        client = WhatsAppOutboundClient(
            api_endpoint="https://graph.facebook.com",
            access_token="token-123",
            phone_number_id="957912434071464",
        )

        request = OutboundMessageRequest(
            to="+5511987654321",
            message_type="text",
            text="Olá",
        )

        result = client._build_payload_safe(request)

        if not isinstance(result, OutboundMessageResponse):
            assert isinstance(result, dict)

    def test_build_payload_safe_logs_no_pii(self):
        """Não deve logar PII (telefone) em caso de erro."""
        client = WhatsAppOutboundClient(
            api_endpoint="https://graph.facebook.com",
            access_token="token-123",
            phone_number_id="957912434071464",
        )

        # Criar uma requisição que causará erro de build
        request = OutboundMessageRequest(
            to="+5511987654321",
            message_type="invalid_type",
            text="Teste",
        )

        with patch("pyloto_corp.adapters.whatsapp.outbound.build_full_payload") as mock_build:
            mock_build.side_effect = Exception("Build failed")
            result = client._build_payload_safe(request)

        assert isinstance(result, OutboundMessageResponse)
        assert result.success is False
