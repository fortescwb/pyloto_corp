"""Testes para tipos adicionais: ADDRESS, LOCATION, TEMPLATE."""

import pytest

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest
from pyloto_corp.adapters.whatsapp.normalizer import extract_messages
from pyloto_corp.adapters.whatsapp.validators import (
    ValidationError,
    WhatsAppMessageValidator,
)


class TestAddressMessageNormalization:
    """Testes de normalização de mensagens de endereço."""

    def test_extract_address_message(self):
        """Testa extração de mensagem de endereço."""
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "id": "msg_address",
                                        "from": "5511999999999",
                                        "timestamp": "1234567890",
                                        "type": "address",
                                        "address": {
                                            "street": "Rua São Bento, 123",
                                            "city": "São Paulo",
                                            "state": "SP",
                                            "zip_code": "01010-100",
                                            "country_code": "BR",
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
        assert messages[0].message_type == "address"
        assert messages[0].address_street == "Rua São Bento, 123"
        assert messages[0].address_city == "São Paulo"
        assert messages[0].address_state == "SP"


class TestAddressMessageValidation:
    """Testes de validação de mensagens de endereço."""

    def test_valid_address_message(self):
        """Testa endereço válido."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="address",
            address_street="Rua São Bento, 123",
            address_city="São Paulo",
            address_state="SP",
        )
        WhatsAppMessageValidator.validate_outbound_request(request)

    def test_address_message_missing_all_fields(self):
        """Testa erro quando nenhum campo de endereço é fornecido."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="address",
        )
        with pytest.raises(
            ValidationError, match="At least one address field is required"
        ):
            WhatsAppMessageValidator.validate_outbound_request(request)


class TestLocationMessageValidation:
    """Testes de validação de mensagens de localização."""

    def test_valid_location_message(self):
        """Testa localização válida."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="location",
            location_latitude=-23.550520,
            location_longitude=-46.633309,
            location_name="Pátio do Colégio",
        )
        WhatsAppMessageValidator.validate_outbound_request(request)

    def test_location_missing_coordinates(self):
        """Testa erro quando coordenadas estão faltando."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="location",
        )
        with pytest.raises(
            ValidationError,
            match="location_latitude and location_longitude are required",
        ):
            WhatsAppMessageValidator.validate_outbound_request(request)

    def test_location_invalid_latitude(self):
        """Testa erro com latitude inválida."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="location",
            location_latitude=95.0,  # > 90
            location_longitude=-46.633309,
        )
        with pytest.raises(
            ValidationError,
            match="location_latitude must be between -90 and 90",
        ):
            WhatsAppMessageValidator.validate_outbound_request(request)

    def test_location_invalid_longitude(self):
        """Testa erro com longitude inválida."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="location",
            location_latitude=-23.550520,
            location_longitude=185.0,  # > 180
        )
        with pytest.raises(
            ValidationError,
            match="location_longitude must be between -180 and 180",
        ):
            WhatsAppMessageValidator.validate_outbound_request(request)


class TestTemplateMessageValidation:
    """Testes de validação de mensagens de template."""

    def test_valid_template_message(self):
        """Testa template válido."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="template",
            template_name="hello_world",
        )
        WhatsAppMessageValidator.validate_outbound_request(request)

    def test_template_message_missing_name(self):
        """Testa erro quando template_name está faltando."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="template",
        )
        with pytest.raises(ValidationError, match="template_name is required"):
            WhatsAppMessageValidator.validate_outbound_request(request)

    def test_template_message_name_too_long(self):
        """Testa erro quando template_name é muito longo."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="template",
            template_name="a" * 513,
        )
        with pytest.raises(
            ValidationError,
            match="template_name must not exceed 512",
        ):
            WhatsAppMessageValidator.validate_outbound_request(request)
