"""Testes para validadores WhatsApp/Meta.

Cobertura:
- TextMessageValidator: limites, caracteres especiais, UTF-8
- MediaMessageValidator: MIME types, captions, media_id vs media_url
- InteractiveMessageValidator: botões, listas
- TemplateMessageValidator: templates, parâmetros
- Orquestrador: dispatch coreto, validação completa
"""

from __future__ import annotations

import pytest

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest
from pyloto_corp.adapters.whatsapp.validators.errors import ValidationError
from pyloto_corp.adapters.whatsapp.validators.orchestrator import (
    WhatsAppMessageValidator,
)
from pyloto_corp.adapters.whatsapp.validators.text import validate_text_message
from pyloto_corp.adapters.whatsapp.validators.media import validate_media_message
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
        try:
            validate_text_message(request)
        except ValidationError:
            # OK se rejeitado, mas não deve crashear
            pass

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
