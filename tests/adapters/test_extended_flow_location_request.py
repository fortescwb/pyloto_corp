"""Testes para tipos interativos FLOW e LOCATION_REQUEST_MESSAGE."""

import pytest

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest
from pyloto_corp.adapters.whatsapp.normalizer import extract_messages
from pyloto_corp.adapters.whatsapp.outbound import WhatsAppOutboundClient
from pyloto_corp.adapters.whatsapp.validators import (
    ValidationError,
    WhatsAppMessageValidator,
)


class TestInteractiveLocationRequestValidation:
    """Testes de validação de mensagens interativas com pedido de localização."""

    def test_valid_location_request_message(self):
        """Testa location_request_message válido."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="interactive",
            interactive_type="location_request_message",
            text="Por favor, compartilhe sua localização",
        )
        WhatsAppMessageValidator.validate_outbound_request(request)

    def test_location_request_rejects_buttons_array(self):
        """Testa que location_request_message não aceita array de botões."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="interactive",
            interactive_type="location_request_message",
            text="Por favor, compartilhe sua localização",
            buttons=[{"id": "btn_1", "title": "Ignorado"}],
        )
        with pytest.raises(ValidationError, match="buttons not allowed"):
            WhatsAppMessageValidator.validate_outbound_request(request)


class TestInteractiveFlowValidation:
    """Testes de validação de mensagens interativas com Flow."""

    def test_valid_flow_message(self):
        """Testa flow válido."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="interactive",
            interactive_type="flow",
            text="Clique para preencher o formulário",
            flow_id="flow_123",
            flow_message_version="3",
            flow_token="token_abc",
            flow_cta="Continuar",
            flow_action="navigate",
        )
        WhatsAppMessageValidator.validate_outbound_request(request)

    @pytest.mark.parametrize(
        "missing_field",
        [
            "flow_id",
            "flow_message_version",
            "flow_token",
            "flow_cta",
            "flow_action",
        ],
    )
    def test_flow_message_missing_required_fields(self, missing_field):
        """Testa erro quando qualquer campo obrigatório de flow está faltando."""
        kwargs = {
            "flow_id": "flow_123",
            "flow_message_version": "3",
            "flow_token": "token_abc",
            "flow_cta": "Continuar",
            "flow_action": "navigate",
        }
        kwargs[missing_field] = None

        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="interactive",
            interactive_type="flow",
            text="Clique para preencher o formulário",
            **kwargs,
        )

        with pytest.raises(ValidationError, match=missing_field):
            WhatsAppMessageValidator.validate_outbound_request(request)


class TestFlowLocationRequestOutboundPayloads:
    """Testes de construção de payloads para Flow e Location Request."""

    @staticmethod
    def _client() -> WhatsAppOutboundClient:
        return WhatsAppOutboundClient(
            api_endpoint="https://graph.facebook.com/v20.0",
            access_token="dummy_token",
            phone_number_id="123456",
        )

    def test_build_location_request_payload(self):
        """Garante payload de location_request_message conforme Meta."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="interactive",
            interactive_type="location_request_message",
            text="Autorize o envio da sua localização",
        )
        WhatsAppMessageValidator.validate_outbound_request(request)

        payload = self._client()._build_payload_safe(request)
        interactive = payload["interactive"]

        assert payload["type"] == "interactive"
        assert interactive["type"] == "location_request_message"
        assert interactive["action"] == {"name": "send_location"}
        assert "buttons" not in interactive["action"]
        assert (
            interactive["body"]["text"]
            == "Autorize o envio da sua localização"
        )

    def test_build_flow_payload(self):
        """Garante payload de flow com parâmetros obrigatórios."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="interactive",
            interactive_type="flow",
            text="Complete o formulário",
            flow_id="flow_123",
            flow_message_version="3",
            flow_token="token_abc",
            flow_cta="Continuar",
            flow_action="navigate",
        )
        WhatsAppMessageValidator.validate_outbound_request(request)

        payload = self._client()._build_payload_safe(request)
        interactive = payload["interactive"]
        action = interactive["action"]
        params = action["parameters"]

        assert interactive["type"] == "flow"
        assert action["name"] == "flow"
        assert "type" not in action
        assert params == {
            "flow_message_version": "3",
            "flow_token": "token_abc",
            "flow_id": "flow_123",
            "flow_cta": "Continuar",
            "flow_action": "navigate",
        }
        assert interactive["body"]["text"] == "Complete o formulário"


class TestInteractiveNormalization:
    """Testes de normalização de mensagens interativas."""

    def test_extract_interactive_cta_url(self):
        """Testa extração de mensagem interativa com CTA URL."""
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "msg_cta",
                                        "from": "5511999999999",
                                        "timestamp": "1234567890",
                                        "type": "interactive",
                                        "interactive": {
                                            "type": "cta_url",
                                            "cta_url_reply": {
                                                "url": "https://example.com/callback",
                                            },
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        messages = extract_messages(payload)
        assert len(messages) == 1
        assert messages[0].message_type == "interactive"
        assert messages[0].interactive_type == "cta_url"
        assert (
            messages[0].interactive_cta_url
            == "https://example.com/callback"
        )
