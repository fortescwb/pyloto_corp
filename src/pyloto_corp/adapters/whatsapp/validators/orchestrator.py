"""Orquestrador de validação para mensagens WhatsApp/Meta."""

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest
from pyloto_corp.adapters.whatsapp.validators.errors import ValidationError
from pyloto_corp.adapters.whatsapp.validators.interactive import (
    validate_interactive_message,
)
from pyloto_corp.adapters.whatsapp.validators.limits import (
    MAX_IDEMPOTENCY_KEY_LENGTH,
)
from pyloto_corp.adapters.whatsapp.validators.media import (
    validate_media_message,
)
from pyloto_corp.adapters.whatsapp.validators.template import (
    validate_address_message,
    validate_contacts_message,
    validate_location_message,
    validate_reaction_message,
    validate_template_message,
)
from pyloto_corp.adapters.whatsapp.validators.text import (
    validate_text_message,
)
from pyloto_corp.domain.enums import MessageCategory, MessageType

# Tipos de mídia
_MEDIA_TYPES = frozenset({
    MessageType.IMAGE,
    MessageType.VIDEO,
    MessageType.AUDIO,
    MessageType.DOCUMENT,
    MessageType.STICKER,
})


class WhatsAppMessageValidator:
    """Validador central para mensagens WhatsApp/Meta.

    Orquestra validadores específicos por tipo de mensagem.
    """

    @classmethod
    def validate_outbound_request(
        cls,
        request: OutboundMessageRequest,
    ) -> None:
        """Valida uma requisição outbound completa.

        Args:
            request: Requisição de envio

        Raises:
            ValidationError: Se a requisição violar regras Meta
        """
        cls._validate_recipient(request)
        msg_type = cls._validate_message_type(request)
        cls._dispatch_type_validation(request, msg_type)
        cls._validate_category(request)
        cls._validate_idempotency(request)

    @classmethod
    def _validate_recipient(cls, request: OutboundMessageRequest) -> None:
        """Valida formato do destinatário."""
        if not request.to or not request.to.startswith("+"):
            raise ValidationError(
                "Recipient must be in E.164 format (e.g., +5511999999999)"
            )

    @classmethod
    def _validate_message_type(
        cls,
        request: OutboundMessageRequest,
    ) -> MessageType:
        """Valida e retorna o tipo de mensagem."""
        try:
            return MessageType(request.message_type)
        except ValueError:
            raise ValidationError(
                f"Invalid message_type: {request.message_type}"
            ) from None

    @classmethod
    def _dispatch_type_validation(
        cls,
        request: OutboundMessageRequest,
        msg_type: MessageType,
    ) -> None:
        """Despacha validação para o validador específico."""
        if msg_type == MessageType.TEXT:
            validate_text_message(request)
        elif msg_type in _MEDIA_TYPES:
            validate_media_message(request, msg_type)
        elif msg_type == MessageType.INTERACTIVE:
            validate_interactive_message(request)
        elif msg_type == MessageType.LOCATION:
            validate_location_message(request)
        elif msg_type == MessageType.ADDRESS:
            validate_address_message(request)
        elif msg_type == MessageType.CONTACTS:
            validate_contacts_message(request)
        elif msg_type == MessageType.REACTION:
            validate_reaction_message(request)
        elif msg_type == MessageType.TEMPLATE:
            validate_template_message(request)

    @classmethod
    def _validate_category(cls, request: OutboundMessageRequest) -> None:
        """Valida categoria se fornecida."""
        if request.category:
            try:
                MessageCategory(request.category)
            except ValueError:
                raise ValidationError(
                    f"Invalid category: {request.category}"
                ) from None

    @classmethod
    def _validate_idempotency(cls, request: OutboundMessageRequest) -> None:
        """Valida chave de idempotência."""
        key = request.idempotency_key
        if key and len(key) > MAX_IDEMPOTENCY_KEY_LENGTH:
            raise ValidationError(
                f"idempotency_key must not exceed {MAX_IDEMPOTENCY_KEY_LENGTH}"
            )
