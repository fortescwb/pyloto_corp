"""Validadores para templates, localização, endereço e outros."""

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest
from pyloto_corp.adapters.whatsapp.validators.errors import ValidationError
from pyloto_corp.adapters.whatsapp.validators.limits import (
    MAX_TEMPLATE_NAME_LENGTH,
)


def validate_template_message(request: OutboundMessageRequest) -> None:
    """Valida mensagem de template.

    Args:
        request: Requisição de envio

    Raises:
        ValidationError: Se template inválido
    """
    if not request.template_name:
        raise ValidationError("template_name is required for TEMPLATE message_type")

    if len(request.template_name) > MAX_TEMPLATE_NAME_LENGTH:
        raise ValidationError(f"template_name must not exceed {MAX_TEMPLATE_NAME_LENGTH} chars")


def validate_location_message(request: OutboundMessageRequest) -> None:
    """Valida mensagem de localização.

    Args:
        request: Requisição de envio

    Raises:
        ValidationError: Se localização inválida
    """
    lat = request.location_latitude
    lon = request.location_longitude

    if lat is None or lon is None:
        raise ValidationError("location_latitude and location_longitude are required")

    if not (-90 <= lat <= 90):
        raise ValidationError("location_latitude must be between -90 and 90")

    if not (-180 <= lon <= 180):
        raise ValidationError("location_longitude must be between -180 and 180")


def validate_address_message(request: OutboundMessageRequest) -> None:
    """Valida mensagem de endereço.

    Args:
        request: Requisição de envio

    Raises:
        ValidationError: Se endereço inválido
    """
    has_any = any(
        [
            request.address_street,
            request.address_city,
            request.address_state,
            request.address_zip_code,
            request.address_country_code,
        ]
    )
    if not has_any:
        raise ValidationError("At least one address field is required")


def validate_contacts_message(request: OutboundMessageRequest) -> None:
    """Valida mensagem de contatos (placeholder)."""
    pass


def validate_reaction_message(request: OutboundMessageRequest) -> None:
    """Valida mensagem de reação (placeholder)."""
    pass
