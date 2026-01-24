"""Validadores de conformidade para mensagens WhatsApp/Meta.

Responsabilidade:
- Validar tipos de mensagem conforme Meta API
- Aplicar limites de tamanho e formato
- Evitar mensagens inválidas antes de envio
- Garantir conformidade com categorias e políticas de cobrança
"""

from __future__ import annotations

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest
from pyloto_corp.domain.enums import InteractiveType, MessageCategory, MessageType


class ValidationError(Exception):
    """Erro de validação de mensagem."""

    pass


class WhatsAppMessageValidator:
    """Validador central para mensagens WhatsApp/Meta."""

    # Limites de tamanho por tipo (bytes)
    MAX_TEXT_LENGTH = 4096
    MAX_CAPTION_LENGTH = 1024
    MAX_BUTTON_TEXT_LENGTH = 20
    MAX_LIST_ITEMS = 10
    MAX_BUTTONS_PER_MESSAGE = 3
    MAX_FILE_SIZE_MB = 100  # Geral

    # Tipos MIME suportados
    SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png"}
    SUPPORTED_VIDEO_TYPES = {"video/mp4", "video/3gpp"}
    SUPPORTED_AUDIO_TYPES = {"audio/aac", "audio/mp4", "audio/amr", "audio/ogg"}
    SUPPORTED_DOCUMENT_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    }

    @classmethod
    def validate_outbound_request(cls, request: OutboundMessageRequest) -> None:
        """Valida uma requisição outbound completa.

        Args:
            request: Requisição de envio

        Raises:
            ValidationError: Se a requisição violar regras Meta
        """
        # Validar telefone
        if not request.to or not request.to.startswith("+"):
            msg = "Recipient must be in E.164 format (e.g., +5511999999999)"
            raise ValidationError(msg)

        # Validar tipo de mensagem
        try:
            msg_type = MessageType(request.message_type)
        except ValueError:
            raise ValidationError(f"Invalid message_type: {request.message_type}") from None

        # Validar conforme tipo
        if msg_type == MessageType.TEXT:
            cls._validate_text_message(request)
        elif msg_type in (
            MessageType.IMAGE,
            MessageType.VIDEO,
            MessageType.AUDIO,
            MessageType.DOCUMENT,
            MessageType.STICKER,
        ):
            cls._validate_media_message(request, msg_type)
        elif msg_type == MessageType.INTERACTIVE:
            cls._validate_interactive_message(request)
        elif msg_type == MessageType.LOCATION:
            cls._validate_location_message(request)
        elif msg_type == MessageType.ADDRESS:
            cls._validate_address_message(request)
        elif msg_type == MessageType.CONTACTS:
            cls._validate_contacts_message(request)
        elif msg_type == MessageType.REACTION:
            cls._validate_reaction_message(request)
        elif msg_type == MessageType.TEMPLATE:
            cls._validate_template_message(request)

        # Validar categoria se fornecida
        if request.category:
            try:
                MessageCategory(request.category)
            except ValueError:
                raise ValidationError(f"Invalid category: {request.category}") from None

        # Validar idempotência
        if request.idempotency_key and len(request.idempotency_key) > 255:
            raise ValidationError("idempotency_key must not exceed 255 characters")

    @classmethod
    def _validate_text_message(cls, request: OutboundMessageRequest) -> None:
        """Valida mensagem de texto."""
        if not request.text:
            raise ValidationError("text is required for TEXT message_type")

        if len(request.text) > cls.MAX_TEXT_LENGTH:
            raise ValidationError(
                f"text exceeds maximum length of {cls.MAX_TEXT_LENGTH} characters"
            )

        if len(request.text.encode("utf-8")) > cls.MAX_TEXT_LENGTH:
            raise ValidationError("text exceeds maximum UTF-8 byte length")

    @classmethod
    def _validate_media_message(
        cls, request: OutboundMessageRequest, msg_type: MessageType
    ) -> None:
        """Valida mensagem com mídia (image, video, audio, document, sticker)."""
        if not request.media_id and not request.media_url:
            raise ValidationError(f"{msg_type} requires either media_id or media_url")

        if (
            msg_type in (MessageType.IMAGE, MessageType.VIDEO, MessageType.DOCUMENT)
            and request.text
            and len(request.text) > cls.MAX_CAPTION_LENGTH
        ):
            raise ValidationError(
                f"caption/text exceeds maximum length of {cls.MAX_CAPTION_LENGTH}"
            )

        # Validar MIME type se fornecido
        if request.media_mime_type:
            cls._validate_mime_type(request.media_mime_type, msg_type)

    @classmethod
    def _validate_mime_type(cls, mime_type: str, msg_type: MessageType) -> None:
        """Valida se MIME type é suportado para o tipo de mensagem."""
        # Mapeamento de tipos de mensagem para MIME types suportados
        mime_type_map = {
            MessageType.IMAGE: cls.SUPPORTED_IMAGE_TYPES,
            MessageType.VIDEO: cls.SUPPORTED_VIDEO_TYPES,
            MessageType.AUDIO: cls.SUPPORTED_AUDIO_TYPES,
            MessageType.DOCUMENT: cls.SUPPORTED_DOCUMENT_TYPES,
        }
        
        supported = mime_type_map.get(msg_type)
        if supported and mime_type not in supported:
            type_name = msg_type.value
            raise ValidationError(
                f"Unsupported {type_name} MIME type: {mime_type}"
            )

    @classmethod
    def _validate_button_interactive(
        cls, request: OutboundMessageRequest
    ) -> None:
        """Valida mensagem interativa do tipo BUTTON."""
        if not request.buttons:
            raise ValidationError(
                "buttons is required for BUTTON interactive type"
            )

        if len(request.buttons) > cls.MAX_BUTTONS_PER_MESSAGE:
            raise ValidationError(
                f"Maximum {cls.MAX_BUTTONS_PER_MESSAGE} buttons allowed"
            )

        for i, btn in enumerate(request.buttons):
            if (
                not isinstance(btn, dict)
                or "id" not in btn
                or "title" not in btn
            ):
                raise ValidationError(
                    f"Button {i} must have 'id' and 'title' fields"
                )

            if len(btn["title"]) > cls.MAX_BUTTON_TEXT_LENGTH:
                raise ValidationError(
                    f"Button {i} title exceeds "
                    f"{cls.MAX_BUTTON_TEXT_LENGTH} characters"
                )

    @classmethod
    def _validate_list_interactive(
        cls, request: OutboundMessageRequest
    ) -> None:
        """Valida mensagem interativa do tipo LIST."""
        if not request.buttons or len(request.buttons) == 0:
            raise ValidationError("At least one list section required")

    @classmethod
    def _validate_flow_interactive(
        cls, request: OutboundMessageRequest
    ) -> None:
        """Valida mensagem interativa do tipo FLOW."""
        missing_fields = [
            field_name
            for field_name, value in {
                "flow_id": request.flow_id,
                "flow_message_version": request.flow_message_version,
                "flow_token": request.flow_token,
                "flow_cta": request.flow_cta,
                "flow_action": request.flow_action,
            }.items()
            if not value
        ]
        if missing_fields:
            raise ValidationError(
                f"{', '.join(missing_fields)} required for FLOW "
                f"interactive type"
            )

        if len(request.flow_cta) > cls.MAX_BUTTON_TEXT_LENGTH:
            raise ValidationError(
                f"flow_cta exceeds {cls.MAX_BUTTON_TEXT_LENGTH} characters"
            )

    @classmethod
    def _validate_cta_url_interactive(
        cls, request: OutboundMessageRequest
    ) -> None:
        """Valida mensagem interativa do tipo CTA_URL."""
        if not request.cta_url:
            raise ValidationError(
                "cta_url is required for CTA_URL interactive type"
            )

        if not request.cta_display_text:
            raise ValidationError(
                "cta_display_text is required for "
                "CTA_URL interactive type"
            )

        if len(request.cta_display_text) > cls.MAX_BUTTON_TEXT_LENGTH:
            raise ValidationError(
                f"cta_display_text exceeds "
                f"{cls.MAX_BUTTON_TEXT_LENGTH} characters"
            )

        if request.buttons:
            raise ValidationError(
                "buttons not allowed for CTA_URL interactive type"
            )

    @classmethod
    def _validate_location_request_interactive(
        cls, request: OutboundMessageRequest
    ) -> None:
        """Valida mensagem interativa do tipo LOCATION_REQUEST_MESSAGE."""
        if request.buttons:
            raise ValidationError(
                "buttons not allowed for LOCATION_REQUEST_MESSAGE "
                "interactive type"
            )

    @classmethod
    def _validate_interactive_message(cls, request: OutboundMessageRequest) -> None:
        """Valida mensagem interativa."""
        if not request.interactive_type:
            raise ValidationError(
                "interactive_type is required for INTERACTIVE message_type"
            )

        try:
            int_type = InteractiveType(request.interactive_type)
        except ValueError:
            msg = f"Invalid interactive_type: {request.interactive_type}"
            raise ValidationError(msg) from None

        if not request.text:
            raise ValidationError(
                "text (body) is required for interactive messages"
            )

        if len(request.text) > cls.MAX_TEXT_LENGTH:
            msg = (
                f"text exceeds maximum length of "
                f"{cls.MAX_TEXT_LENGTH} characters"
            )
            raise ValidationError(msg)

        # Validar conforme tipo interativo específico
        cls._validate_interactive_type(int_type, request)

    @classmethod
    def _validate_interactive_type(
        cls, int_type: InteractiveType, request: OutboundMessageRequest
    ) -> None:
        """Despacha validação para tipo interativo específico."""
        validator_map = {
            InteractiveType.BUTTON: cls._validate_button_interactive,
            InteractiveType.LIST: cls._validate_list_interactive,
            InteractiveType.FLOW: cls._validate_flow_interactive,
            InteractiveType.CTA_URL: cls._validate_cta_url_interactive,
            InteractiveType.LOCATION_REQUEST_MESSAGE: (
                cls._validate_location_request_interactive
            ),
        }
        validator = validator_map.get(int_type)
        if validator:
            validator(request)

    @classmethod
    def _validate_address_message(cls, request: OutboundMessageRequest) -> None:
        """Valida mensagem de endereço."""
        # At least one field should be provided
        if not any([
            request.address_street,
            request.address_city,
            request.address_state,
            request.address_zip_code,
            request.address_country_code,
        ]):
            raise ValidationError("At least one address field is required")

    @classmethod
    def _validate_location_message(cls, request: OutboundMessageRequest) -> None:
        """Valida mensagem de localização."""
        if (request.location_latitude is None or 
                request.location_longitude is None):
            raise ValidationError(
                "location_latitude and location_longitude are required"
            )

        if not (-90 <= request.location_latitude <= 90):
            raise ValidationError(
                "location_latitude must be between -90 and 90"
            )

        if not (-180 <= request.location_longitude <= 180):
            raise ValidationError(
                "location_longitude must be between -180 and 180"
            )

    @classmethod
    def _validate_contacts_message(cls, request: OutboundMessageRequest) -> None:
        """Valida mensagem de contatos."""
        # Será implementado quando necessário
        pass

    @classmethod
    def _validate_reaction_message(cls, request: OutboundMessageRequest) -> None:
        """Valida mensagem de reação."""
        # Será implementado quando necessário
        pass

    @classmethod
    def _validate_template_message(cls, request: OutboundMessageRequest) -> None:
        """Valida mensagem de template."""
        if not request.template_name:
            raise ValidationError("template_name is required for TEMPLATE message_type")

        if len(request.template_name) > 512:
            raise ValidationError("template_name must not exceed 512 characters")
