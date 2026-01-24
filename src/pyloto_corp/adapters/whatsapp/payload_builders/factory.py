"""Factory para obter o builder correto por tipo de mensagem."""

from __future__ import annotations

from typing import Any

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest
from pyloto_corp.adapters.whatsapp.payload_builders.base import (
    PayloadBuilder,
    build_base_payload,
)
from pyloto_corp.adapters.whatsapp.payload_builders.interactive import (
    InteractivePayloadBuilder,
)
from pyloto_corp.adapters.whatsapp.payload_builders.location import (
    AddressPayloadBuilder,
    LocationPayloadBuilder,
)
from pyloto_corp.adapters.whatsapp.payload_builders.media import (
    AudioPayloadBuilder,
    DocumentPayloadBuilder,
    ImagePayloadBuilder,
    VideoPayloadBuilder,
)
from pyloto_corp.adapters.whatsapp.payload_builders.template import (
    TemplatePayloadBuilder,
)
from pyloto_corp.adapters.whatsapp.payload_builders.text import (
    TextPayloadBuilder,
)
from pyloto_corp.domain.enums import MessageType

# Mapeamento de tipo de mensagem para builder
_BUILDERS: dict[MessageType, PayloadBuilder] = {
    MessageType.TEXT: TextPayloadBuilder(),
    MessageType.IMAGE: ImagePayloadBuilder(),
    MessageType.VIDEO: VideoPayloadBuilder(),
    MessageType.AUDIO: AudioPayloadBuilder(),
    MessageType.DOCUMENT: DocumentPayloadBuilder(),
    MessageType.LOCATION: LocationPayloadBuilder(),
    MessageType.ADDRESS: AddressPayloadBuilder(),
    MessageType.INTERACTIVE: InteractivePayloadBuilder(),
}

_TEMPLATE_BUILDER = TemplatePayloadBuilder()


def get_payload_builder(message_type: MessageType) -> PayloadBuilder | None:
    """Retorna o builder para o tipo de mensagem.

    Args:
        message_type: Tipo de mensagem

    Returns:
        Builder apropriado ou None se não suportado
    """
    return _BUILDERS.get(message_type)


def build_full_payload(request: OutboundMessageRequest) -> dict[str, Any]:
    """Constrói payload completo para a API Meta.

    Args:
        request: Requisição de envio

    Returns:
        Payload completo pronto para envio

    Raises:
        ValueError: Se tipo de mensagem não suportado
    """
    payload = build_base_payload(request)

    # Template tem prioridade sobre tipo de mensagem
    if request.template_name:
        payload.update(_TEMPLATE_BUILDER.build(request))
        return payload

    # Obtém builder pelo tipo
    msg_type = MessageType(request.message_type)
    builder = get_payload_builder(msg_type)

    if builder is None:
        raise ValueError(f"Tipo de mensagem não suportado: {msg_type}")

    payload.update(builder.build(request))
    return payload
