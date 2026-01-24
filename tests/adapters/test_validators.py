"""Testes para o módulo de validação WhatsApp."""

import pytest

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest
from pyloto_corp.adapters.whatsapp.validators import ValidationError, WhatsAppMessageValidator


class TestTextMessageValidation:
    """Testes de validação para mensagens de texto."""

    def test_valid_text_message(self):
        """Testa validação de mensagem de texto válida."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="text",
            text="Olá, tudo bem?",
        )
        # Não deve lançar exceção
        WhatsAppMessageValidator.validate_outbound_request(request)

    def test_text_message_missing_body(self):
        """Testa que texto é obrigatório."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="text",
            text=None,
        )
        with pytest.raises(ValidationError, match="text is required"):
            WhatsAppMessageValidator.validate_outbound_request(request)

    def test_text_message_exceeds_max_length(self):
        """Testa limite de tamanho de texto."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="text",
            text="x" * (WhatsAppMessageValidator.MAX_TEXT_LENGTH + 1),
        )
        with pytest.raises(ValidationError, match="exceeds maximum length"):
            WhatsAppMessageValidator.validate_outbound_request(request)


class TestMediaMessageValidation:
    """Testes de validação para mensagens com mídia."""

    def test_valid_image_with_media_id(self):
        """Testa imagem válida com media_id."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="image",
            media_id="image_id_123",
        )
        WhatsAppMessageValidator.validate_outbound_request(request)

    def test_valid_image_with_media_url(self):
        """Testa imagem válida com media_url."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="image",
            media_url="https://example.com/image.jpg",
        )
        WhatsAppMessageValidator.validate_outbound_request(request)

    def test_image_missing_media_id_and_url(self):
        """Testa que image requer media_id ou media_url."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="image",
        )
        with pytest.raises(ValidationError, match="requires either media_id or media_url"):
            WhatsAppMessageValidator.validate_outbound_request(request)

    def test_image_with_caption(self):
        """Testa imagem com legenda."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="image",
            media_id="image_id_123",
            text="Descrição da imagem",
        )
        WhatsAppMessageValidator.validate_outbound_request(request)

    def test_image_caption_exceeds_max_length(self):
        """Testa limite de tamanho de legenda."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="image",
            media_id="image_id_123",
            text="x" * (WhatsAppMessageValidator.MAX_CAPTION_LENGTH + 1),
        )
        with pytest.raises(ValidationError, match="caption/text exceeds maximum"):
            WhatsAppMessageValidator.validate_outbound_request(request)


class TestInteractiveMessageValidation:
    """Testes de validação para mensagens interativas."""

    def test_valid_button_message(self):
        """Testa mensagem interativa com botões válida."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="interactive",
            interactive_type="button",
            text="Escolha uma opção",
            buttons=[
                {"id": "btn_1", "title": "Opção 1"},
                {"id": "btn_2", "title": "Opção 2"},
            ],
        )
        WhatsAppMessageValidator.validate_outbound_request(request)

    def test_button_message_missing_interactive_type(self):
        """Testa que interactive_type é obrigatório."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="interactive",
            text="Escolha",
        )
        with pytest.raises(ValidationError, match="interactive_type is required"):
            WhatsAppMessageValidator.validate_outbound_request(request)

    def test_button_message_missing_body(self):
        """Testa que body (text) é obrigatório."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="interactive",
            interactive_type="button",
            buttons=[{"id": "btn_1", "title": "Opção"}],
        )
        with pytest.raises(ValidationError, match="text.*is required"):
            WhatsAppMessageValidator.validate_outbound_request(request)

    def test_button_message_missing_buttons(self):
        """Testa que buttons é obrigatório para BUTTON type."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="interactive",
            interactive_type="button",
            text="Escolha",
        )
        with pytest.raises(ValidationError, match="buttons is required"):
            WhatsAppMessageValidator.validate_outbound_request(request)

    def test_button_message_exceeds_max_buttons(self):
        """Testa limite de quantidade de botões."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="interactive",
            interactive_type="button",
            text="Escolha",
            buttons=[
                {"id": f"btn_{i}", "title": f"Opção {i}"}
                for i in range(WhatsAppMessageValidator.MAX_BUTTONS_PER_MESSAGE + 1)
            ],
        )
        with pytest.raises(ValidationError, match="Maximum.*buttons allowed"):
            WhatsAppMessageValidator.validate_outbound_request(request)

    def test_button_text_exceeds_max_length(self):
        """Testa limite de tamanho de texto do botão."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="interactive",
            interactive_type="button",
            text="Escolha",
            buttons=[
                {
                    "id": "btn_1",
                    "title": "x" * (WhatsAppMessageValidator.MAX_BUTTON_TEXT_LENGTH + 1),
                }
            ],
        )
        with pytest.raises(ValidationError, match="exceeds"):
            WhatsAppMessageValidator.validate_outbound_request(request)


class TestPhoneValidation:
    """Testes de validação de número de telefone."""

    def test_valid_e164_phone(self):
        """Testa validação de telefone E.164."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="text",
            text="Olá",
        )
        WhatsAppMessageValidator.validate_outbound_request(request)

    def test_invalid_phone_no_plus(self):
        """Testa que telefone sem + é inválido."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type="text",
            text="Olá",
        )
        with pytest.raises(ValidationError, match="E.164 format"):
            WhatsAppMessageValidator.validate_outbound_request(request)

    def test_invalid_phone_empty(self):
        """Testa que telefone vazio é inválido."""
        request = OutboundMessageRequest(
            to="",
            message_type="text",
            text="Olá",
        )
        with pytest.raises(ValidationError, match="E.164 format"):
            WhatsAppMessageValidator.validate_outbound_request(request)


class TestCategoryValidation:
    """Testes de validação de categorias."""

    def test_valid_category_marketing(self):
        """Testa categoria MARKETING válida."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="text",
            text="Promoção especial",
            category="MARKETING",
        )
        WhatsAppMessageValidator.validate_outbound_request(request)

    def test_valid_category_utility(self):
        """Testa categoria UTILITY válida."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="text",
            text="Seu pedido foi confirmado",
            category="UTILITY",
        )
        WhatsAppMessageValidator.validate_outbound_request(request)

    def test_invalid_category(self):
        """Testa categoria inválida."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type="text",
            text="Mensagem",
            category="INVALID_CATEGORY",
        )
        with pytest.raises(ValidationError, match="Invalid category"):
            WhatsAppMessageValidator.validate_outbound_request(request)
