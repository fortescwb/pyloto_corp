"""Validadores de conformidade para mensagens WhatsApp/Meta.

Este pacote contém validadores especializados por tipo de mensagem,
separando responsabilidades conforme regras_e_padroes.md.

Uso:
    from pyloto_corp.adapters.whatsapp.validators import (
        WhatsAppMessageValidator,
        ValidationError,
    )

    validator = WhatsAppMessageValidator()
    validator.validate_outbound_request(request)
"""

from pyloto_corp.adapters.whatsapp.validators.errors import (
    ValidationError,
)
from pyloto_corp.adapters.whatsapp.validators.limits import (
    MAX_BUTTON_TEXT_LENGTH,
    MAX_BUTTONS_PER_MESSAGE,
    MAX_CAPTION_LENGTH,
    MAX_TEXT_LENGTH,
)
from pyloto_corp.adapters.whatsapp.validators.orchestrator import (
    WhatsAppMessageValidator,
)

# Adiciona constantes como atributos de classe para compatibilidade
WhatsAppMessageValidator.MAX_TEXT_LENGTH = MAX_TEXT_LENGTH
WhatsAppMessageValidator.MAX_CAPTION_LENGTH = MAX_CAPTION_LENGTH
WhatsAppMessageValidator.MAX_BUTTONS_PER_MESSAGE = MAX_BUTTONS_PER_MESSAGE
WhatsAppMessageValidator.MAX_BUTTON_TEXT_LENGTH = MAX_BUTTON_TEXT_LENGTH

__all__ = [
    "ValidationError",
    "WhatsAppMessageValidator",
    "MAX_TEXT_LENGTH",
    "MAX_CAPTION_LENGTH",
    "MAX_BUTTONS_PER_MESSAGE",
    "MAX_BUTTON_TEXT_LENGTH",
]
