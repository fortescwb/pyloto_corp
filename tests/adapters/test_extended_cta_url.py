"""Testes para tipo interativo CTA_URL."""

import pytest

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest
from pyloto_corp.adapters.whatsapp.outbound import WhatsAppOutboundClient
from pyloto_corp.adapters.whatsapp.validators import (
    ValidationError,
    WhatsAppMessageValidator,
)


class TestInteractiveCTAURLValidation:
    """Testes de validação de mensagens interativas com CTA URL."""

    def test_valid_cta_url_message(self):
        """Testa CTA URL válido."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="interactive",
            interactive_type="cta_url",
            text="Clique para mais informações",
            cta_url="https://example.com/info",
            cta_display_text="Saiba Mais",
        )
        WhatsAppMessageValidator.validate_outbound_request(request)

    def test_cta_url_missing_url(self):
        """Testa erro quando URL está faltando."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="interactive",
            interactive_type="cta_url",
            text="Clique para mais informações",
            cta_display_text="Saiba Mais",
        )
        with pytest.raises(ValidationError, match="cta_url is required"):
            WhatsAppMessageValidator.validate_outbound_request(request)

    def test_cta_url_missing_display_text(self):
        """Testa erro quando display_text está faltando."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="interactive",
            interactive_type="cta_url",
            text="Clique para mais informações",
            cta_url="https://example.com/info",
        )
        with pytest.raises(ValidationError, match="cta_display_text is required"):
            WhatsAppMessageValidator.validate_outbound_request(request)

    def test_cta_url_display_text_too_long(self):
        """Testa erro quando display_text é muito longo."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="interactive",
            interactive_type="cta_url",
            text="Clique para mais informações",
            cta_url="https://example.com/info",
            cta_display_text="a" * 21,
        )
        with pytest.raises(ValidationError, match="cta_display_text exceeds"):
            WhatsAppMessageValidator.validate_outbound_request(request)

    def test_cta_url_rejects_buttons_array(self):
        """Testa que CTA_URL não aceita array de botões."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="interactive",
            interactive_type="cta_url",
            text="Clique para mais informações",
            cta_url="https://example.com/info",
            cta_display_text="Saiba Mais",
            buttons=[{"id": "btn_1", "title": "Ignorado"}],
        )
        with pytest.raises(ValidationError, match="buttons not allowed"):
            WhatsAppMessageValidator.validate_outbound_request(request)


class TestCTAURLOutboundPayloads:
    """Testes de construção de payloads CTA_URL outbound."""

    @staticmethod
    def _client() -> WhatsAppOutboundClient:
        return WhatsAppOutboundClient(
            api_endpoint="https://graph.facebook.com/v20.0",
            access_token="dummy_token",
            phone_number_id="123456",
        )

    def test_build_cta_url_payload(self):
        """Garante payload de cta_url sem array de botões."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="interactive",
            interactive_type="cta_url",
            text="Acesse o portal",
            cta_url="https://example.com/portal",
            cta_display_text="Abrir",
        )
        WhatsAppMessageValidator.validate_outbound_request(request)

        payload = self._client()._build_payload_safe(request)
        interactive = payload["interactive"]
        action = interactive["action"]

        assert interactive["type"] == "cta_url"
        assert action["name"] == "cta_url"
        assert action["parameters"] == {
            "display_text": "Abrir",
            "url": "https://example.com/portal",
        }
        assert "buttons" not in action
        assert interactive["body"]["text"] == "Acesse o portal"
