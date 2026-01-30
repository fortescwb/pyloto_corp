"""Validadores para mensagens de texto."""

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest
from pyloto_corp.adapters.whatsapp.validators.errors import ValidationError
from pyloto_corp.adapters.whatsapp.validators.limits import MAX_TEXT_LENGTH


def validate_text_message(request: OutboundMessageRequest) -> None:
    """Valida mensagem de texto.

    Args:
        request: Requisição de envio

    Raises:
        ValidationError: Se texto ausente ou excede limite
    """
    if not request.text:
        raise ValidationError("text is required for TEXT message_type")

    if len(request.text) > MAX_TEXT_LENGTH:
        raise ValidationError(f"text exceeds maximum length of {MAX_TEXT_LENGTH} characters")

    if len(request.text.encode("utf-8")) > MAX_TEXT_LENGTH:
        raise ValidationError("text exceeds maximum UTF-8 byte length")
