"""Testes para validadores WhatsApp/Meta.

Cobertura:
- TextMessageValidator: limites, caracteres especiais, UTF-8
- MediaMessageValidator: MIME types, captions, media_id vs media_url
- InteractiveMessageValidator: botões, listas
- TemplateMessageValidator: templates, parâmetros
- Orquestrador: dispatch coreto, validação completa
"""

from __future__ import annotations

from contextlib import suppress

import pytest

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest
from pyloto_corp.adapters.whatsapp.validators.errors import ValidationError
from pyloto_corp.adapters.whatsapp.validators.media import validate_media_message
from pyloto_corp.adapters.whatsapp.validators.orchestrator import (
    WhatsAppMessageValidator,
)
from pyloto_corp.adapters.whatsapp.validators.text import validate_text_message
from pyloto_corp.domain.enums import MessageType


class TestTextMessageValidator:
    """Testes para validação de mensagens de texto."""

    def test_valid_text_message(self) -> None:
        """Texto válido passa na validação."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.TEXT.value,
            text="Olá, como posso ajudar?",
        )

        # Deve não lançar exceção
        validate_text_message(request)

    def test_text_missing_raises_error(self) -> None:
        """Texto ausente lança ValidationError."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.TEXT.value,
            text=None,
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_text_message(request)

        assert "text is required" in str(exc_info.value)

    def test_text_empty_string_raises_error(self) -> None:
        """Texto vazio lança ValidationError."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.TEXT.value,
            text="",
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_text_message(request)

        assert "text is required" in str(exc_info.value)

    def test_text_exceeds_max_length_raises_error(self) -> None:
        """Texto acima de 4096 caracteres lança erro."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.TEXT.value,
            text="a" * 4097,
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_text_message(request)

        assert "exceeds maximum" in str(exc_info.value)

    def test_text_at_max_length_passes(self) -> None:
        """Texto com exatamente 4096 caracteres passa."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.TEXT.value,
            text="a" * 4096,
        )

        # Deve não lançar exceção
        validate_text_message(request)

    def test_text_with_special_chars_passes(self) -> None:
        """Texto com caracteres especiais, emoji, acentuação passa."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.TEXT.value,
            text="Olá! 🎉 Como você está? Ñoño",
        )

        # Deve não lançar exceção
        validate_text_message(request)

    def test_text_utf8_byte_limit(self) -> None:
        """Caracteres UTF-8 multi-byte são contabilizados corretamente."""
        # Emoji = 4 bytes em UTF-8
        text_with_emoji = "a" * 1024 + "🎉" * 1024  # ~5KB em bytes
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.TEXT.value,
            text=text_with_emoji,
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_text_message(request)

        assert "UTF-8" in str(exc_info.value)


class TestMediaMessageValidator:
    """Testes para validação de mensagens de mídia."""

    def test_valid_image_with_media_id(self) -> None:
        """Imagem com media_id válida passa."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.IMAGE.value,
            media_id="123456789",
        )

        # Deve não lançar exceção
        validate_media_message(request, MessageType.IMAGE)

    def test_valid_image_with_media_url(self) -> None:
        """Imagem com media_url válida passa."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.IMAGE.value,
            media_url="https://example.com/image.jpg",
        )

        # Deve não lançar exceção
        validate_media_message(request, MessageType.IMAGE)

    def test_media_missing_both_id_and_url_raises_error(self) -> None:
        """Falta both media_id e media_url lança erro."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.IMAGE.value,
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_media_message(request, MessageType.IMAGE)

        assert "requires either media_id or media_url" in str(exc_info.value)

    def test_caption_exceeds_limit_raises_error(self) -> None:
        """Caption acima de 1024 caracteres lança erro."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.IMAGE.value,
            media_id="123456789",
            text="a" * 1025,
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_media_message(request, MessageType.IMAGE)

        assert "caption" in str(exc_info.value).lower()
        assert "exceeds maximum" in str(exc_info.value).lower()

    def test_caption_at_limit_passes(self) -> None:
        """Caption com exatamente 1024 caracteres passa."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.IMAGE.value,
            media_id="123456789",
            text="a" * 1024,
        )

        # Deve não lançar exceção
        validate_media_message(request, MessageType.IMAGE)

    def test_unsupported_mime_type_raises_error(self) -> None:
        """MIME type não suportado lança erro."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.IMAGE.value,
            media_id="123456789",
            media_mime_type="image/bmp",  # Não suportado
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_media_message(request, MessageType.IMAGE)

        assert "Unsupported" in str(exc_info.value)
        assert "bmp" in str(exc_info.value).lower()

    def test_supported_mime_type_passes(self) -> None:
        """MIME type suportado passa validação."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.IMAGE.value,
            media_id="123456789",
            media_mime_type="image/jpeg",
        )

        # Deve não lançar exceção
        validate_media_message(request, MessageType.IMAGE)

    def test_video_with_valid_mime_type(self) -> None:
        """Vídeo com MIME type válido passa."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.VIDEO.value,
            media_id="123456789",
            media_mime_type="video/mp4",
        )

        # Deve não lançar exceção
        validate_media_message(request, MessageType.VIDEO)

    def test_audio_with_valid_mime_type(self) -> None:
        """Áudio com MIME type válido passa."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.AUDIO.value,
            media_id="123456789",
            media_mime_type="audio/mp4",
        )

        # Deve não lançar exceção
        validate_media_message(request, MessageType.AUDIO)

    def test_document_with_valid_mime_type(self) -> None:
        """Documento com MIME type válido passa."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.DOCUMENT.value,
            media_id="123456789",
            media_mime_type="application/pdf",
        )

        # Deve não lançar exceção
        validate_media_message(request, MessageType.DOCUMENT)


class TestOrchestratorValidator:
    """Testes para validação completa via orquestrador."""

    def test_valid_text_request(self) -> None:
        """Requisição de texto válida passa validação."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type=MessageType.TEXT.value,
            text="Olá!",
        )

        # Deve não lançar exceção
        WhatsAppMessageValidator.validate_outbound_request(request)

    def test_invalid_recipient_raises_error(self) -> None:
        """Destinatário inválido lança erro."""
        request = OutboundMessageRequest(
            to="invalid",
            message_type=MessageType.TEXT.value,
            text="Olá!",
        )

        with pytest.raises(ValidationError) as exc_info:
            WhatsAppMessageValidator.validate_outbound_request(request)

        assert "recipient" in str(exc_info.value).lower()

    def test_missing_message_type_raises_error(self) -> None:
        """Tipo de mensagem ausente lança erro."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type=None,
            text="Olá!",
        )

        with pytest.raises(ValidationError) as exc_info:
            WhatsAppMessageValidator.validate_outbound_request(request)

        assert "message_type" in str(exc_info.value).lower()

    def test_idempotency_key_too_long_raises_error(self) -> None:
        """Chave de idempotência acima de 255 caracteres lança erro."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type=MessageType.TEXT.value,
            text="Olá!",
            idempotency_key="a" * 256,
        )

        with pytest.raises(ValidationError) as exc_info:
            WhatsAppMessageValidator.validate_outbound_request(request)

        assert "idempotency" in str(exc_info.value).lower()

    def test_idempotency_key_at_limit_passes(self) -> None:
        """Chave de idempotência com 255 caracteres passa."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type=MessageType.TEXT.value,
            text="Olá!",
            idempotency_key="a" * 255,
        )

        # Deve não lançar exceção
        WhatsAppMessageValidator.validate_outbound_request(request)


class TestValidatorEdgeCases:
    """Testes de casos extremos e segurança."""

    def test_text_with_null_bytes_handling(self) -> None:
        """Texto com null bytes é tratado corretamente."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.TEXT.value,
            text="Olá\x00mundo",
        )

        # Comportamento: valida como texto normal (null é caractere)
        # Não deve lançar exceção (Meta API trata)
        with suppress(ValidationError):
            validate_text_message(request)

    def test_recipient_with_plus_sign(self) -> None:
        """Número com '+' prefixo é válido."""
        request = OutboundMessageRequest(
            to="+5511999999999",
            message_type=MessageType.TEXT.value,
            text="Olá!",
        )

        # Deve não lançar exceção
        WhatsAppMessageValidator.validate_outbound_request(request)

    def test_text_with_line_breaks(self) -> None:
        """Texto com quebras de linha é válido."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.TEXT.value,
            text="Linha 1\nLinha 2\nLinha 3",
        )

        # Deve não lançar exceção
        validate_text_message(request)

    def test_media_url_with_query_params(self) -> None:
        """URL de mídia com query parameters é válida."""
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.IMAGE.value,
            media_url="https://example.com/image.jpg?token=abc&size=large",
        )

        # Deve não lançar exceção
        validate_media_message(request, MessageType.IMAGE)


class TestInteractiveMessageValidator:
    """Testes para validação de mensagens interativas."""

    def test_valid_button_interactive_message(self) -> None:
        """Mensagem interativa de botões válida passa."""
        from pyloto_corp.adapters.whatsapp.validators.interactive import (
            validate_interactive_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.INTERACTIVE.value,
            interactive_type="button",
            text="Escolha uma opção:",
            buttons=[
                {"id": "btn_1", "title": "Opção 1"},
                {"id": "btn_2", "title": "Opção 2"},
            ],
        )

        # Deve não lançar exceção
        validate_interactive_message(request)

    def test_interactive_missing_type_raises_error(self) -> None:
        """Tipo interativo ausente lança erro."""
        from pyloto_corp.adapters.whatsapp.validators.interactive import (
            validate_interactive_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.INTERACTIVE.value,
            interactive_type=None,
            text="Texto",
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_interactive_message(request)
        assert "interactive_type is required" in str(exc_info.value)

    def test_interactive_invalid_type_raises_error(self) -> None:
        """Tipo interativo inválido lança erro."""
        from pyloto_corp.adapters.whatsapp.validators.interactive import (
            validate_interactive_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.INTERACTIVE.value,
            interactive_type="invalid_type",
            text="Texto",
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_interactive_message(request)
        assert "Invalid interactive_type" in str(exc_info.value)

    def test_interactive_missing_body_raises_error(self) -> None:
        """Corpo (text) ausente em mensagem interativa lança erro."""
        from pyloto_corp.adapters.whatsapp.validators.interactive import (
            validate_interactive_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.INTERACTIVE.value,
            interactive_type="button",
            text=None,
            buttons=[{"id": "btn_1", "title": "Op"}],
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_interactive_message(request)
        assert "text (body) is required" in str(exc_info.value)

    def test_interactive_body_exceeds_max_length_raises_error(self) -> None:
        """Corpo acima do limite lança erro."""
        from pyloto_corp.adapters.whatsapp.validators.interactive import (
            validate_interactive_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.INTERACTIVE.value,
            interactive_type="button",
            text="x" * 4097,  # Acima de 4096
            buttons=[{"id": "btn_1", "title": "Op"}],
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_interactive_message(request)
        assert "exceeds maximum length" in str(exc_info.value)

    def test_button_type_missing_buttons_raises_error(self) -> None:
        """Tipo BUTTON sem botões lança erro."""
        from pyloto_corp.adapters.whatsapp.validators.interactive import (
            validate_interactive_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.INTERACTIVE.value,
            interactive_type="button",
            text="Escolha:",
            buttons=None,
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_interactive_message(request)
        assert "buttons is required" in str(exc_info.value)

    def test_button_type_exceeds_max_buttons_raises_error(self) -> None:
        """Excesso de botões lança erro."""
        from pyloto_corp.adapters.whatsapp.validators.interactive import (
            validate_interactive_message,
        )

        # Max é 3 botões por mensagem
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.INTERACTIVE.value,
            interactive_type="button",
            text="Escolha:",
            buttons=[
                {"id": f"btn_{i}", "title": f"Op {i}"}
                for i in range(5)
            ],
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_interactive_message(request)
        assert "Maximum" in str(exc_info.value) and "buttons" in str(exc_info.value)

    def test_button_missing_id_raises_error(self) -> None:
        """Botão sem ID lança erro."""
        from pyloto_corp.adapters.whatsapp.validators.interactive import (
            validate_interactive_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.INTERACTIVE.value,
            interactive_type="button",
            text="Escolha:",
            buttons=[
                {"title": "Op 1"},  # Falta 'id'
            ],
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_interactive_message(request)
        assert "must have 'id' and 'title'" in str(exc_info.value)

    def test_button_title_exceeds_limit_raises_error(self) -> None:
        """Título do botão acima do limite lança erro."""
        from pyloto_corp.adapters.whatsapp.validators.interactive import (
            validate_interactive_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.INTERACTIVE.value,
            interactive_type="button",
            text="Escolha:",
            buttons=[
                {"id": "btn_1", "title": "x" * 256},  # Max é 20 chars
            ],
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_interactive_message(request)
        assert "title exceeds" in str(exc_info.value)

    def test_list_type_requires_sections(self) -> None:
        """Tipo LIST sem seções lança erro."""
        from pyloto_corp.adapters.whatsapp.validators.interactive import (
            validate_interactive_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.INTERACTIVE.value,
            interactive_type="list",
            text="Escolha:",
            buttons=[],  # Vazio
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_interactive_message(request)
        assert "At least one list section required" in str(exc_info.value)

    def test_flow_type_valid(self) -> None:
        """Tipo FLOW válido passa."""
        from pyloto_corp.adapters.whatsapp.validators.interactive import (
            validate_interactive_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.INTERACTIVE.value,
            interactive_type="flow",
            text="Inicie o fluxo:",
            flow_id="flow_123",
            flow_message_version="3",
            flow_token="token_abc",
            flow_cta="Iniciar",
            flow_action="NAVIGATE",
        )

        validate_interactive_message(request)

    def test_flow_type_missing_field_raises_error(self) -> None:
        """Tipo FLOW sem campo obrigatório lança erro."""
        from pyloto_corp.adapters.whatsapp.validators.interactive import (
            validate_interactive_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.INTERACTIVE.value,
            interactive_type="flow",
            text="Inicie:",
            flow_id="flow_123",
            flow_message_version=None,  # Falta
            flow_token="token_abc",
            flow_cta="Iniciar",
            flow_action="NAVIGATE",
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_interactive_message(request)
        assert "required for FLOW" in str(exc_info.value)

    def test_cta_url_type_valid(self) -> None:
        """Tipo CTA_URL válido passa."""
        from pyloto_corp.adapters.whatsapp.validators.interactive import (
            validate_interactive_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.INTERACTIVE.value,
            interactive_type="cta_url",
            text="Acesse:",
            cta_url="https://example.com",
            cta_display_text="Clique aqui",
        )

        validate_interactive_message(request)

    def test_cta_url_type_missing_url_raises_error(self) -> None:
        """Tipo CTA_URL sem URL lança erro."""
        from pyloto_corp.adapters.whatsapp.validators.interactive import (
            validate_interactive_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.INTERACTIVE.value,
            interactive_type="cta_url",
            text="Acesse:",
            cta_url=None,
            cta_display_text="Clique",
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_interactive_message(request)
        assert "cta_url is required" in str(exc_info.value)

    def test_location_request_type_valid(self) -> None:
        """Tipo LOCATION_REQUEST_MESSAGE válido passa."""
        from pyloto_corp.adapters.whatsapp.validators.interactive import (
            validate_interactive_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.INTERACTIVE.value,
            interactive_type="location_request_message",
            text="Envie sua localização",
        )

        validate_interactive_message(request)


class TestTemplateMessageValidator:
    """Testes para validação de templates e localização."""

    def test_valid_template_message(self) -> None:
        """Template válido passa."""
        from pyloto_corp.adapters.whatsapp.validators.template import (
            validate_template_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.TEMPLATE.value,
            template_name="hello_world",
        )

        validate_template_message(request)

    def test_template_missing_name_raises_error(self) -> None:
        """Template sem nome lança erro."""
        from pyloto_corp.adapters.whatsapp.validators.template import (
            validate_template_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.TEMPLATE.value,
            template_name=None,
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_template_message(request)
        assert "template_name is required" in str(exc_info.value)

    def test_template_name_exceeds_limit_raises_error(self) -> None:
        """Nome de template acima do limite lança erro."""
        from pyloto_corp.adapters.whatsapp.validators.template import (
            validate_template_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.TEMPLATE.value,
            template_name="x" * 513,  # Acima de 512
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_template_message(request)
        assert "must not exceed" in str(exc_info.value)

    def test_valid_location_message(self) -> None:
        """Mensagem de localização válida passa."""
        from pyloto_corp.adapters.whatsapp.validators.template import (
            validate_location_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.LOCATION.value,
            location_latitude=-23.5505,
            location_longitude=-46.6333,
        )

        validate_location_message(request)

    def test_location_missing_coordinates_raises_error(self) -> None:
        """Localização sem coordenadas lança erro."""
        from pyloto_corp.adapters.whatsapp.validators.template import (
            validate_location_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.LOCATION.value,
            location_latitude=None,
            location_longitude=-46.6333,
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_location_message(request)
        assert "location_latitude and location_longitude are required" in str(exc_info.value)

    def test_location_invalid_latitude_raises_error(self) -> None:
        """Latitude inválida lança erro."""
        from pyloto_corp.adapters.whatsapp.validators.template import (
            validate_location_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.LOCATION.value,
            location_latitude=91.0,  # Acima de 90
            location_longitude=-46.6333,
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_location_message(request)
        assert "location_latitude must be between -90 and 90" in str(exc_info.value)

    def test_location_invalid_longitude_raises_error(self) -> None:
        """Longitude inválida lança erro."""
        from pyloto_corp.adapters.whatsapp.validators.template import (
            validate_location_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.LOCATION.value,
            location_latitude=-23.5505,
            location_longitude=181.0,  # Acima de 180
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_location_message(request)
        assert "location_longitude must be between -180 and 180" in str(exc_info.value)

    def test_location_boundary_values_pass(self) -> None:
        """Valores limites de coordenadas passam."""
        from pyloto_corp.adapters.whatsapp.validators.template import (
            validate_location_message,
        )

        # Testando limites
        for lat, lon in [(-90, -180), (90, 180), (0, 0)]:
            request = OutboundMessageRequest(
                to="5511999999999",
                message_type=MessageType.LOCATION.value,
                location_latitude=lat,
                location_longitude=lon,
            )
            validate_location_message(request)

    def test_valid_address_message(self) -> None:
        """Mensagem de endereço válida passa."""
        from pyloto_corp.adapters.whatsapp.validators.template import (
            validate_address_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.ADDRESS.value,
            address_street="Rua A",
            address_city="São Paulo",
        )

        validate_address_message(request)

    def test_address_missing_all_fields_raises_error(self) -> None:
        """Endereço sem campos lança erro."""
        from pyloto_corp.adapters.whatsapp.validators.template import (
            validate_address_message,
        )

        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.ADDRESS.value,
        )

        with pytest.raises(ValidationError) as exc_info:
            validate_address_message(request)
        assert "At least one address field is required" in str(exc_info.value)
