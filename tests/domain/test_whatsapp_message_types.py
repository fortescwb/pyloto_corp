"""Testes para tipos de mensagens WhatsApp."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pyloto_corp.domain.whatsapp_message_types import (
    AddressMessage,
    AudioMessage,
    ButtonReply,
    ContactMessage,
    DocumentMessage,
    ImageMessage,
    InteractiveButtonMessage,
    InteractiveCTAURLMessage,
    InteractiveFlowMessage,
    InteractiveListMessage,
    InteractiveLocationRequestMessage,
    ListItem,
    LocationMessage,
    ReactionMessage,
    StickerMessage,
    TemplateMessage,
    TextMessage,
    VideoMessage,
    MessageMetadata,
)


class TestTextMessage:
    """Testes para TextMessage."""

    def test_text_message_valid(self):
        """Deve criar TextMessage válida."""
        msg = TextMessage(body="Olá, tudo bem?", preview_url=False)
        assert msg.body == "Olá, tudo bem?"
        assert msg.preview_url is False

    def test_text_message_with_preview_url(self):
        """Deve criar TextMessage com preview de URL."""
        msg = TextMessage(body="Confira: https://example.com", preview_url=True)
        assert msg.preview_url is True

    def test_text_message_empty_body_invalid(self):
        """Deve rejeitar TextMessage com body vazio."""
        with pytest.raises(ValidationError):
            TextMessage(body="")

    def test_text_message_max_length(self):
        """Deve respeitar comprimento máximo de 4096."""
        msg = TextMessage(body="x" * 4096)
        assert len(msg.body) == 4096

    def test_text_message_exceeds_max_length(self):
        """Deve rejeitar body acima de 4096 caracteres."""
        with pytest.raises(ValidationError):
            TextMessage(body="x" * 4097)


class TestImageMessage:
    """Testes para ImageMessage."""

    def test_image_message_with_url(self):
        """Deve criar ImageMessage com URL."""
        msg = ImageMessage(url="https://example.com/image.jpg")
        assert msg.url == "https://example.com/image.jpg"

    def test_image_message_with_id(self):
        """Deve criar ImageMessage com ID de mídia."""
        msg = ImageMessage(id="image-id-123")
        assert msg.id == "image-id-123"

    def test_image_message_with_caption(self):
        """Deve criar ImageMessage com caption."""
        msg = ImageMessage(url="https://example.com/img.jpg", caption="Foto de teste")
        assert msg.caption == "Foto de teste"

    def test_image_message_no_id_or_url_invalid(self):
        """Deve rejeitar ImageMessage sem ID ou URL."""
        with pytest.raises(ValueError):
            ImageMessage()

    def test_image_message_caption_max_length(self):
        """Deve respeitar comprimento máximo de caption."""
        msg = ImageMessage(url="https://example.com/img.jpg", caption="x" * 1024)
        assert len(msg.caption) == 1024

    def test_image_message_caption_exceeds_max(self):
        """Deve rejeitar caption acima de 1024."""
        with pytest.raises(ValidationError):
            ImageMessage(url="https://example.com/img.jpg", caption="x" * 1025)


class TestVideoMessage:
    """Testes para VideoMessage."""

    def test_video_message_with_url(self):
        """Deve criar VideoMessage com URL."""
        msg = VideoMessage(url="https://example.com/video.mp4")
        assert msg.url == "https://example.com/video.mp4"

    def test_video_message_with_id(self):
        """Deve criar VideoMessage com ID."""
        msg = VideoMessage(id="video-id-123")
        assert msg.id == "video-id-123"

    def test_video_message_no_id_or_url_invalid(self):
        """Deve rejeitar VideoMessage sem ID ou URL."""
        with pytest.raises(ValueError):
            VideoMessage()

    def test_video_message_with_caption(self):
        """Deve criar VideoMessage com caption."""
        msg = VideoMessage(url="https://example.com/video.mp4", caption="Vídeo teste")
        assert msg.caption == "Vídeo teste"


class TestAudioMessage:
    """Testes para AudioMessage."""

    def test_audio_message_with_url(self):
        """Deve criar AudioMessage com URL."""
        msg = AudioMessage(url="https://example.com/audio.aac")
        assert msg.url == "https://example.com/audio.aac"

    def test_audio_message_with_id(self):
        """Deve criar AudioMessage com ID."""
        msg = AudioMessage(id="audio-id-123")
        assert msg.id == "audio-id-123"

    def test_audio_message_no_id_or_url_invalid(self):
        """Deve rejeitar AudioMessage sem ID ou URL."""
        with pytest.raises(ValueError):
            AudioMessage()


class TestDocumentMessage:
    """Testes para DocumentMessage."""

    def test_document_message_with_url(self):
        """Deve criar DocumentMessage com URL."""
        msg = DocumentMessage(url="https://example.com/doc.pdf")
        assert msg.url == "https://example.com/doc.pdf"

    def test_document_message_with_filename(self):
        """Deve criar DocumentMessage com filename."""
        msg = DocumentMessage(url="https://example.com/doc.pdf", filename="relatório.pdf")
        assert msg.filename == "relatório.pdf"

    def test_document_message_with_caption(self):
        """Deve criar DocumentMessage com caption."""
        msg = DocumentMessage(
            url="https://example.com/doc.pdf", caption="Documento importante"
        )
        assert msg.caption == "Documento importante"

    def test_document_message_no_id_or_url_invalid(self):
        """Deve rejeitar DocumentMessage sem ID ou URL."""
        with pytest.raises(ValueError):
            DocumentMessage()


class TestStickerMessage:
    """Testes para StickerMessage."""

    def test_sticker_message_with_url(self):
        """Deve criar StickerMessage com URL."""
        msg = StickerMessage(url="https://example.com/sticker.webp")
        assert msg.url == "https://example.com/sticker.webp"

    def test_sticker_message_with_id(self):
        """Deve criar StickerMessage com ID."""
        msg = StickerMessage(id="sticker-id-123")
        assert msg.id == "sticker-id-123"

    def test_sticker_message_no_id_or_url_invalid(self):
        """Deve rejeitar StickerMessage sem ID ou URL."""
        with pytest.raises(ValueError):
            StickerMessage()


class TestLocationMessage:
    """Testes para LocationMessage."""

    def test_location_message_valid(self):
        """Deve criar LocationMessage válida."""
        msg = LocationMessage(latitude=-23.5505, longitude=-46.6333)
        assert msg.latitude == -23.5505
        assert msg.longitude == -46.6333

    def test_location_message_with_name(self):
        """Deve criar LocationMessage com nome."""
        msg = LocationMessage(
            latitude=-23.5505, longitude=-46.6333, name="São Paulo, SP"
        )
        assert msg.name == "São Paulo, SP"

    def test_location_message_with_address(self):
        """Deve criar LocationMessage com endereço."""
        msg = LocationMessage(
            latitude=-23.5505,
            longitude=-46.6333,
            name="Pyloto",
            address="Av. Paulista, 1000",
        )
        assert msg.address == "Av. Paulista, 1000"

    def test_location_message_lat_long_required(self):
        """Latitude e longitude são obrigatórias."""
        with pytest.raises(ValidationError):
            LocationMessage(latitude=-23.5505)


class TestContactMessage:
    """Testes para ContactMessage."""

    def test_contact_message_valid(self):
        """Deve criar ContactMessage válida."""
        msg = ContactMessage(name="João Silva")
        assert msg.name == "João Silva"

    def test_contact_message_with_phones(self):
        """Deve criar ContactMessage com telefones."""
        msg = ContactMessage(
            name="João Silva", phones=["+5511987654321", "+5511912345678"]
        )
        assert len(msg.phones) == 2

    def test_contact_message_with_emails(self):
        """Deve criar ContactMessage com emails."""
        msg = ContactMessage(name="João Silva", emails=["joao@example.com"])
        assert msg.emails == ["joao@example.com"]

    def test_contact_message_with_organization(self):
        """Deve criar ContactMessage com organização."""
        msg = ContactMessage(name="João Silva", organization="Pyloto")
        assert msg.organization == "Pyloto"

    def test_contact_message_name_required(self):
        """Nome é obrigatório."""
        with pytest.raises(ValidationError):
            ContactMessage(name="")


class TestAddressMessage:
    """Testes para AddressMessage."""

    def test_address_message_empty(self):
        """Deve criar AddressMessage vazia (campos opcionais)."""
        msg = AddressMessage()
        assert msg.street is None
        assert msg.city is None

    def test_address_message_full(self):
        """Deve criar AddressMessage completa."""
        msg = AddressMessage(
            street="Av. Paulista, 1000",
            city="São Paulo",
            state="SP",
            zip_code="01311-100",
            country_code="BR",
            country="Brasil",
            notes="Apto 101",
        )
        assert msg.street == "Av. Paulista, 1000"
        assert msg.city == "São Paulo"

    def test_address_message_notes_max_length(self):
        """Deve respeitar comprimento máximo de notes."""
        msg = AddressMessage(notes="x" * 1024)
        assert len(msg.notes) == 1024


class TestTemplateMessage:
    """Testes para TemplateMessage."""

    def test_template_message_valid(self):
        """Deve criar TemplateMessage válida."""
        msg = TemplateMessage(namespace="hello", name="hello_world")
        assert msg.namespace == "hello"
        assert msg.name == "hello_world"

    def test_template_message_with_language(self):
        """Deve criar TemplateMessage com idioma customizado."""
        msg = TemplateMessage(namespace="hello", name="hello_world", language="en_US")
        assert msg.language == "en_US"

    def test_template_message_default_language(self):
        """Deve usar pt_BR como idioma padrão."""
        msg = TemplateMessage(namespace="hello", name="hello_world")
        assert msg.language == "pt_BR"

    def test_template_message_with_parameters(self):
        """Deve criar TemplateMessage com parâmetros."""
        msg = TemplateMessage(
            namespace="hello",
            name="hello_world",
            parameters={"name": "João", "value": 42},
        )
        assert msg.parameters == {"name": "João", "value": 42}

    def test_template_message_with_category(self):
        """Deve criar TemplateMessage com categoria."""
        msg = TemplateMessage(
            namespace="hello", name="hello_world", category="MARKETING"
        )
        assert msg.category == "MARKETING"

    def test_template_message_namespace_required(self):
        """Namespace é obrigatório."""
        with pytest.raises(ValidationError):
            TemplateMessage(namespace="", name="hello_world")

    def test_template_message_name_required(self):
        """Name é obrigatório."""
        with pytest.raises(ValidationError):
            TemplateMessage(namespace="hello", name="")


class TestButtonReply:
    """Testes para ButtonReply."""

    def test_button_reply_valid(self):
        """Deve criar ButtonReply válida."""
        btn = ButtonReply(id="btn-1", title="Opção 1")
        assert btn.id == "btn-1"
        assert btn.title == "Opção 1"

    def test_button_reply_slots(self):
        """ButtonReply deve usar slots para eficiência."""
        btn = ButtonReply(id="btn-1", title="Opção 1")
        # Verificar que é dataclass com slots
        assert hasattr(ButtonReply, "__slots__")


class TestListItem:
    """Testes para ListItem."""

    def test_list_item_valid(self):
        """Deve criar ListItem válida."""
        item = ListItem(id="item-1", title="Item 1")
        assert item.id == "item-1"
        assert item.title == "Item 1"

    def test_list_item_with_description(self):
        """Deve criar ListItem com descrição."""
        item = ListItem(id="item-1", title="Item 1", description="Descrição do item")
        assert item.description == "Descrição do item"


class TestInteractiveButtonMessage:
    """Testes para InteractiveButtonMessage."""

    def test_interactive_button_message_valid(self):
        """Deve criar InteractiveButtonMessage válida."""
        msg = InteractiveButtonMessage(
            body="Escolha uma opção",
            buttons=[
                ButtonReply(id="1", title="Opção 1"),
                ButtonReply(id="2", title="Opção 2"),
            ],
        )
        assert len(msg.buttons) == 2

    def test_interactive_button_message_max_buttons(self):
        """Deve respeitar máximo de 3 botões."""
        msg = InteractiveButtonMessage(
            body="Escolha",
            buttons=[
                ButtonReply(id="1", title="Opção 1"),
                ButtonReply(id="2", title="Opção 2"),
                ButtonReply(id="3", title="Opção 3"),
            ],
        )
        assert len(msg.buttons) == 3

    def test_interactive_button_message_exceeds_max_buttons(self):
        """Deve rejeitar mais de 3 botões."""
        with pytest.raises(ValidationError):
            InteractiveButtonMessage(
                body="Escolha",
                buttons=[
                    ButtonReply(id="1", title="Opção 1"),
                    ButtonReply(id="2", title="Opção 2"),
                    ButtonReply(id="3", title="Opção 3"),
                    ButtonReply(id="4", title="Opção 4"),
                ],
            )

    def test_interactive_button_message_with_footer(self):
        """Deve criar InteractiveButtonMessage com footer."""
        msg = InteractiveButtonMessage(
            body="Escolha",
            buttons=[ButtonReply(id="1", title="Opção 1")],
            footer="Rodapé",
        )
        assert msg.footer == "Rodapé"


class TestInteractiveListMessage:
    """Testes para InteractiveListMessage."""

    def test_interactive_list_message_valid(self):
        """Deve criar InteractiveListMessage válida."""
        msg = InteractiveListMessage(
            body="Escolha uma opção",
            button="Ver opções",
            sections=[{"id": "1", "title": "Seção 1", "rows": []}],
        )
        assert msg.button == "Ver opções"
        assert len(msg.sections) == 1


class TestInteractiveFlowMessage:
    """Testes para InteractiveFlowMessage."""

    def test_interactive_flow_message_valid(self):
        """Deve criar InteractiveFlowMessage válida."""
        msg = InteractiveFlowMessage(
            flow_message_version="3",
            flow_token="token-123",
            flow_id="flow-123",
            flow_cta="Iniciar",
            flow_action="navigate",
        )
        assert msg.flow_id == "flow-123"

    def test_interactive_flow_message_with_body(self):
        """Deve criar InteractiveFlowMessage com body."""
        msg = InteractiveFlowMessage(
            flow_message_version="3",
            flow_token="token-123",
            flow_id="flow-123",
            flow_cta="Iniciar",
            flow_action="navigate",
            body="Preencha o formulário",
        )
        assert msg.body == "Preencha o formulário"


class TestInteractiveCTAURLMessage:
    """Testes para InteractiveCTAURLMessage."""

    def test_interactive_cta_url_message_valid(self):
        """Deve criar InteractiveCTAURLMessage válida."""
        msg = InteractiveCTAURLMessage(
            body="Visite nosso site",
            cta_url="https://example.com",
            cta_display_text="Acessar",
        )
        assert msg.cta_url == "https://example.com"

    def test_interactive_cta_url_message_with_footer(self):
        """Deve criar InteractiveCTAURLMessage com footer."""
        msg = InteractiveCTAURLMessage(
            body="Visite nosso site",
            cta_url="https://example.com",
            cta_display_text="Acessar",
            footer="Powered by Pyloto",
        )
        assert msg.footer == "Powered by Pyloto"


class TestInteractiveLocationRequestMessage:
    """Testes para InteractiveLocationRequestMessage."""

    def test_interactive_location_request_valid(self):
        """Deve criar InteractiveLocationRequestMessage válida."""
        msg = InteractiveLocationRequestMessage(
            body="Por favor, compartilhe sua localização"
        )
        assert msg.body == "Por favor, compartilhe sua localização"

    def test_interactive_location_request_with_footer(self):
        """Deve criar InteractiveLocationRequestMessage com footer."""
        msg = InteractiveLocationRequestMessage(
            body="Por favor, compartilhe sua localização", footer="Seguro"
        )
        assert msg.footer == "Seguro"


class TestReactionMessage:
    """Testes para ReactionMessage."""

    def test_reaction_message_valid(self):
        """Deve criar ReactionMessage válida."""
        msg = ReactionMessage(message_id="msg-123", emoji="👍")
        assert msg.message_id == "msg-123"
        assert msg.emoji == "👍"

    def test_reaction_message_emoji_max_length(self):
        """Emoji deve ter até 2 caracteres."""
        msg = ReactionMessage(message_id="msg-123", emoji="👍")
        assert len(msg.emoji) <= 2

    def test_reaction_message_emoji_required(self):
        """Emoji é obrigatório."""
        with pytest.raises(ValidationError):
            ReactionMessage(message_id="msg-123", emoji="")


class TestMessageMetadata:
    """Testes para MessageMetadata."""

    def test_message_metadata_valid(self):
        """Deve criar MessageMetadata válida."""
        meta = MessageMetadata(
            message_id="msg-123",
            timestamp=1704067200,
            from_number="+5511987654321",
            message_type="text",
        )
        assert meta.message_id == "msg-123"
        assert meta.timestamp == 1704067200

    def test_message_metadata_optional_fields(self):
        """Deve criar MessageMetadata com campos opcionais."""
        meta = MessageMetadata(
            message_id="msg-123",
            timestamp=1704067200,
            from_number="+5511987654321",
            message_type="image",
            category="MARKETING",
            media_url="https://example.com/image.jpg",
            media_type="image/jpeg",
        )
        assert meta.category == "MARKETING"
        assert meta.media_url == "https://example.com/image.jpg"
