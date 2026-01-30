"""Validadores para mensagens de mídia (imagem, vídeo, áudio, documento)."""

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest
from pyloto_corp.adapters.whatsapp.validators.errors import ValidationError
from pyloto_corp.adapters.whatsapp.validators.limits import (
    MAX_CAPTION_LENGTH,
    SUPPORTED_AUDIO_TYPES,
    SUPPORTED_DOCUMENT_TYPES,
    SUPPORTED_IMAGE_TYPES,
    SUPPORTED_VIDEO_TYPES,
)
from pyloto_corp.domain.enums import MessageType

# Mapeamento de tipo para MIME types suportados
_MIME_TYPE_MAP: dict[MessageType, frozenset[str]] = {
    MessageType.IMAGE: SUPPORTED_IMAGE_TYPES,
    MessageType.VIDEO: SUPPORTED_VIDEO_TYPES,
    MessageType.AUDIO: SUPPORTED_AUDIO_TYPES,
    MessageType.DOCUMENT: SUPPORTED_DOCUMENT_TYPES,
}

# Tipos que suportam caption
_TYPES_WITH_CAPTION = frozenset(
    {
        MessageType.IMAGE,
        MessageType.VIDEO,
        MessageType.DOCUMENT,
    }
)


def validate_media_message(
    request: OutboundMessageRequest,
    msg_type: MessageType,
) -> None:
    """Valida mensagem de mídia.

    Args:
        request: Requisição de envio
        msg_type: Tipo de mídia

    Raises:
        ValidationError: Se mídia inválida
    """
    if not request.media_id and not request.media_url:
        raise ValidationError(f"{msg_type.value} requires either media_id or media_url")

    # Validar caption se aplicável
    text_exceeds = request.text and len(request.text) > MAX_CAPTION_LENGTH
    if msg_type in _TYPES_WITH_CAPTION and text_exceeds:
        raise ValidationError(f"caption/text exceeds maximum of {MAX_CAPTION_LENGTH}")

    # Validar MIME type se fornecido
    if request.media_mime_type:
        _validate_mime_type(request.media_mime_type, msg_type)


def _validate_mime_type(mime_type: str, msg_type: MessageType) -> None:
    """Valida se MIME type é suportado para o tipo de mensagem."""
    supported = _MIME_TYPE_MAP.get(msg_type)
    if supported and mime_type not in supported:
        raise ValidationError(f"Unsupported {msg_type.value} MIME type: {mime_type}")
