"""Testes para builders de payload WhatsApp.

Cobertura:
- Factory: seleção correta de builders por tipo
- TextPayloadBuilder: estrutura de texto
- MediaPayloadBuilders: imagem, vídeo, áudio, documento
- InteractivePayloadBuilder: botões, listas, flows
- LocationPayloadBuilder: localização, endereço
- TemplatePayloadBuilder: templates
"""

from __future__ import annotations

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest
from pyloto_corp.adapters.whatsapp.payload_builders.factory import (
    get_payload_builder,
)
from pyloto_corp.domain.enums import MessageType


class TestPayloadBuilderFactory:
    """Testes para factory de seleção de builders."""

    def test_factory_returns_text_builder(self) -> None:
        """Factory retorna TextPayloadBuilder para TEXT."""
        builder = get_payload_builder(MessageType.TEXT)
        assert builder is not None
        assert builder.__class__.__name__ == "TextPayloadBuilder"

    def test_factory_returns_image_builder(self) -> None:
        """Factory retorna ImagePayloadBuilder para IMAGE."""
        builder = get_payload_builder(MessageType.IMAGE)
        assert builder is not None
        assert builder.__class__.__name__ == "ImagePayloadBuilder"

    def test_factory_returns_video_builder(self) -> None:
        """Factory retorna VideoPayloadBuilder para VIDEO."""
        builder = get_payload_builder(MessageType.VIDEO)
        assert builder is not None
        assert builder.__class__.__name__ == "VideoPayloadBuilder"

    def test_factory_returns_audio_builder(self) -> None:
        """Factory retorna AudioPayloadBuilder para AUDIO."""
        builder = get_payload_builder(MessageType.AUDIO)
        assert builder is not None
        assert builder.__class__.__name__ == "AudioPayloadBuilder"

    def test_factory_returns_document_builder(self) -> None:
        """Factory retorna DocumentPayloadBuilder para DOCUMENT."""
        builder = get_payload_builder(MessageType.DOCUMENT)
        assert builder is not None
        assert builder.__class__.__name__ == "DocumentPayloadBuilder"

    def test_factory_returns_location_builder(self) -> None:
        """Factory retorna LocationPayloadBuilder para LOCATION."""
        builder = get_payload_builder(MessageType.LOCATION)
        assert builder is not None
        assert builder.__class__.__name__ == "LocationPayloadBuilder"

    def test_factory_returns_address_builder(self) -> None:
        """Factory retorna AddressPayloadBuilder para ADDRESS."""
        builder = get_payload_builder(MessageType.ADDRESS)
        assert builder is not None
        assert builder.__class__.__name__ == "AddressPayloadBuilder"

    def test_factory_returns_interactive_builder(self) -> None:
        """Factory retorna InteractivePayloadBuilder para INTERACTIVE."""
        builder = get_payload_builder(MessageType.INTERACTIVE)
        assert builder is not None
        assert builder.__class__.__name__ == "InteractivePayloadBuilder"

    def test_factory_returns_none_for_unsupported_type(self) -> None:
        """Factory retorna None para tipo não suportado."""
        builder = get_payload_builder(MessageType.STICKER)
        assert builder is None

    def test_factory_returns_none_for_template_standard(self) -> None:
        """Factory retorna None para TEMPLATE (requer builder especial)."""
        builder = get_payload_builder(MessageType.TEMPLATE)
        assert builder is None


class TestTextPayloadBuilder:
    """Testes para construtor de payload de texto."""

    def test_builds_valid_text_payload(self) -> None:
        """Constrói payload válido de texto."""
        from pyloto_corp.adapters.whatsapp.payload_builders.text import (
            TextPayloadBuilder,
        )

        builder = TextPayloadBuilder()
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.TEXT.value,
            text="Olá!",
        )

        payload = builder.build(request)

        assert payload is not None
        assert "text" in payload
        assert payload["text"]["body"] == "Olá!"
        assert "preview_url" in payload["text"]

    def test_text_payload_default_preview_url_false(self) -> None:
        """Payload de texto com preview URL padrão (False)."""
        from pyloto_corp.adapters.whatsapp.payload_builders.text import (
            TextPayloadBuilder,
        )

        builder = TextPayloadBuilder()
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.TEXT.value,
            text="https://example.com",
        )

        payload = builder.build(request)

        assert payload is not None
        # Builder sempre retorna preview_url=False
        assert payload["text"]["preview_url"] is False


class TestMediaPayloadBuilders:
    """Testes para builders de mídia (imagem, vídeo, áudio, documento)."""

    def test_builds_valid_image_payload_with_id(self) -> None:
        """Constrói payload válido de imagem com media_id."""
        from pyloto_corp.adapters.whatsapp.payload_builders.media import (
            ImagePayloadBuilder,
        )

        builder = ImagePayloadBuilder()
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.IMAGE.value,
            media_id="123456789",
            caption="Imagem",
        )

        payload = builder.build(request)

        assert payload is not None
        assert "image" in payload
        assert payload["image"]["id"] == "123456789"

    def test_builds_valid_image_payload_with_url(self) -> None:
        """Constrói payload válido de imagem com URL."""
        from pyloto_corp.adapters.whatsapp.payload_builders.media import (
            ImagePayloadBuilder,
        )

        builder = ImagePayloadBuilder()
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.IMAGE.value,
            media_url="https://example.com/image.jpg",
        )

        payload = builder.build(request)

        assert payload is not None
        assert "image" in payload
        assert payload["image"]["link"] == "https://example.com/image.jpg"

    def test_builds_valid_video_payload(self) -> None:
        """Constrói payload válido de vídeo."""
        from pyloto_corp.adapters.whatsapp.payload_builders.media import (
            VideoPayloadBuilder,
        )

        builder = VideoPayloadBuilder()
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.VIDEO.value,
            media_id="987654321",
            caption="Vídeo",
        )

        payload = builder.build(request)

        assert payload is not None
        assert "video" in payload
        assert payload["video"]["id"] == "987654321"

    def test_builds_valid_audio_payload(self) -> None:
        """Constrói payload válido de áudio."""
        from pyloto_corp.adapters.whatsapp.payload_builders.media import (
            AudioPayloadBuilder,
        )

        builder = AudioPayloadBuilder()
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.AUDIO.value,
            media_url="https://example.com/audio.mp3",
        )

        payload = builder.build(request)

        assert payload is not None
        assert "audio" in payload
        assert payload["audio"]["link"] == "https://example.com/audio.mp3"

    def test_builds_valid_document_payload(self) -> None:
        """Constrói payload válido de documento."""
        from pyloto_corp.adapters.whatsapp.payload_builders.media import (
            DocumentPayloadBuilder,
        )

        builder = DocumentPayloadBuilder()
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.DOCUMENT.value,
            media_id="doc_123",
            caption="Doc",
        )

        payload = builder.build(request)

        assert payload is not None
        assert "document" in payload
        assert payload["document"]["id"] == "doc_123"


class TestInteractivePayloadBuilder:
    """Testes para construtor de payload interativo."""

    def test_builds_valid_button_payload(self) -> None:
        """Constrói payload válido com botões."""
        from pyloto_corp.adapters.whatsapp.payload_builders.interactive import (
            InteractivePayloadBuilder,
        )

        builder = InteractivePayloadBuilder()
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.INTERACTIVE.value,
            interactive_type="button",
            text="Escolha:",
            buttons=[
                {"id": "btn_1", "title": "Opção 1"},
                {"id": "btn_2", "title": "Opção 2"},
            ],
        )

        payload = builder.build(request)

        assert payload is not None
        assert "interactive" in payload
        interactive = payload["interactive"]
        assert interactive["type"] == "button"
        assert interactive["body"]["text"] == "Escolha:"
        assert len(interactive["action"]["buttons"]) == 2

    def test_builds_valid_list_payload(self) -> None:
        """Constrói payload válido com lista."""
        from pyloto_corp.adapters.whatsapp.payload_builders.interactive import (
            InteractivePayloadBuilder,
        )

        builder = InteractivePayloadBuilder()
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.INTERACTIVE.value,
            interactive_type="list",
            text="Escolha:",
            buttons=[{"id": "section_1", "title": "Seção 1"}],
        )

        payload = builder.build(request)

        assert payload is not None
        assert payload["interactive"]["type"] == "list"

    def test_builds_valid_flow_payload(self) -> None:
        """Constrói payload válido com flow."""
        from pyloto_corp.adapters.whatsapp.payload_builders.interactive import (
            InteractivePayloadBuilder,
        )

        builder = InteractivePayloadBuilder()
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.INTERACTIVE.value,
            interactive_type="flow",
            text="Inicie:",
            flow_id="flow_123",
            flow_message_version="3",
            flow_token="token_abc",
            flow_cta="Iniciar",
            flow_action="NAVIGATE",
        )

        payload = builder.build(request)

        assert payload is not None
        assert payload["interactive"]["type"] == "flow"


class TestLocationPayloadBuilder:
    """Testes para construtor de payload de localização."""

    def test_builds_valid_location_payload(self) -> None:
        """Constrói payload válido de localização."""
        from pyloto_corp.adapters.whatsapp.payload_builders.location import (
            LocationPayloadBuilder,
        )

        builder = LocationPayloadBuilder()
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.LOCATION.value,
            location_latitude=-23.5505,
            location_longitude=-46.6333,
        )

        payload = builder.build(request)

        assert payload is not None
        assert "location" in payload
        assert payload["location"]["latitude"] == -23.5505
        assert payload["location"]["longitude"] == -46.6333


class TestTemplatePayloadBuilder:
    """Testes para construtor de payload de template."""

    def test_builds_valid_template_payload(self) -> None:
        """Constrói payload válido de template."""
        from pyloto_corp.adapters.whatsapp.payload_builders.template import (
            TemplatePayloadBuilder,
        )

        builder = TemplatePayloadBuilder()
        request = OutboundMessageRequest(
            to="5511999999999",
            message_type=MessageType.TEMPLATE.value,
            template_name="hello_world",
            template_language="en_US",
        )

        payload = builder.build(request)

        assert payload is not None
        assert "template" in payload
        assert payload["template"]["name"] == "hello_world"
