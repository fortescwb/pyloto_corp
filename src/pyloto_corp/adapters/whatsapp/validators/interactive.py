"""Validadores para mensagens interativas."""

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest
from pyloto_corp.adapters.whatsapp.validators.errors import ValidationError
from pyloto_corp.adapters.whatsapp.validators.limits import (
    MAX_BUTTON_TEXT_LENGTH,
    MAX_BUTTONS_PER_MESSAGE,
    MAX_TEXT_LENGTH,
)
from pyloto_corp.domain.enums import InteractiveType


def validate_interactive_message(request: OutboundMessageRequest) -> None:
    """Valida mensagem interativa.

    Args:
        request: Requisição de envio

    Raises:
        ValidationError: Se interativa inválida
    """
    if not request.interactive_type:
        raise ValidationError(
            "interactive_type is required for INTERACTIVE message_type"
        )

    try:
        int_type = InteractiveType(request.interactive_type)
    except ValueError:
        raise ValidationError(
            f"Invalid interactive_type: {request.interactive_type}"
        ) from None

    if not request.text:
        raise ValidationError(
            "text (body) is required for interactive messages"
        )

    if len(request.text) > MAX_TEXT_LENGTH:
        raise ValidationError(
            f"text exceeds maximum length of {MAX_TEXT_LENGTH} characters"
        )

    # Despacha para validador específico
    _VALIDATORS.get(int_type, lambda r: None)(request)


def _validate_button(request: OutboundMessageRequest) -> None:
    """Valida tipo BUTTON."""
    if not request.buttons:
        raise ValidationError(
            "buttons is required for BUTTON interactive type"
        )

    if len(request.buttons) > MAX_BUTTONS_PER_MESSAGE:
        raise ValidationError(
            f"Maximum {MAX_BUTTONS_PER_MESSAGE} buttons allowed"
        )

    for i, btn in enumerate(request.buttons):
        if not isinstance(btn, dict) or "id" not in btn or "title" not in btn:
            raise ValidationError(
                f"Button {i} must have 'id' and 'title' fields"
            )
        if len(btn["title"]) > MAX_BUTTON_TEXT_LENGTH:
            raise ValidationError(
                f"Button {i} title exceeds {MAX_BUTTON_TEXT_LENGTH} chars"
            )


def _validate_list(request: OutboundMessageRequest) -> None:
    """Valida tipo LIST."""
    if not request.buttons or len(request.buttons) == 0:
        raise ValidationError("At least one list section required")


def _validate_flow(request: OutboundMessageRequest) -> None:
    """Valida tipo FLOW."""
    required = {
        "flow_id": request.flow_id,
        "flow_message_version": request.flow_message_version,
        "flow_token": request.flow_token,
        "flow_cta": request.flow_cta,
        "flow_action": request.flow_action,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise ValidationError(
            f"{', '.join(missing)} required for FLOW interactive type"
        )

    if request.flow_cta and len(request.flow_cta) > MAX_BUTTON_TEXT_LENGTH:
        raise ValidationError(
            f"flow_cta exceeds {MAX_BUTTON_TEXT_LENGTH} characters"
        )


def _validate_cta_url(request: OutboundMessageRequest) -> None:
    """Valida tipo CTA_URL."""
    if not request.cta_url:
        raise ValidationError(
            "cta_url is required for CTA_URL interactive type"
        )

    if not request.cta_display_text:
        raise ValidationError(
            "cta_display_text is required for CTA_URL interactive type"
        )

    if len(request.cta_display_text) > MAX_BUTTON_TEXT_LENGTH:
        raise ValidationError(
            f"cta_display_text exceeds {MAX_BUTTON_TEXT_LENGTH} characters"
        )

    if request.buttons:
        raise ValidationError(
            "buttons not allowed for CTA_URL interactive type"
        )


def _validate_location_request(request: OutboundMessageRequest) -> None:
    """Valida tipo LOCATION_REQUEST_MESSAGE."""
    if request.buttons:
        raise ValidationError(
            "buttons not allowed for LOCATION_REQUEST_MESSAGE type"
        )


# Mapeamento de tipo interativo para validador
_VALIDATORS = {
    InteractiveType.BUTTON: _validate_button,
    InteractiveType.LIST: _validate_list,
    InteractiveType.FLOW: _validate_flow,
    InteractiveType.CTA_URL: _validate_cta_url,
    InteractiveType.LOCATION_REQUEST_MESSAGE: _validate_location_request,
}
