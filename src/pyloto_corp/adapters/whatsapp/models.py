"""Modelos normalizados para WhatsApp.

Responsabilidade:
- Estruturar payloads do webhook da Meta
- Normalizar diferentes tipos de mensagem em formato comum
- Preservar apenas metadados essenciais (sem PII ou payload bruto)
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NormalizedWhatsAppMessage(BaseModel):
    """Mensagem normalizada para consumo do core.

    Campo message_type sempre reflete o tipo técnico do Meta:
    text, image, video, audio, document, sticker, location, contacts, 
    address, reaction, interactive, template.
    """

    message_id: str
    from_number: str | None = None
    timestamp: str | None = None
    message_type: str  # text, image, video, audio, document, sticker, address, etc.
    text: str | None = None
    media_id: str | None = None
    media_url: str | None = None  # Preenchido se houver
    media_filename: str | None = None
    media_mime_type: str | None = None
    # Para location
    location_latitude: float | None = None
    location_longitude: float | None = None
    location_name: str | None = None
    location_address: str | None = None
    # Para address
    address_street: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip_code: str | None = None
    address_country_code: str | None = None
    # Para contacts
    contacts_json: str | None = None  # Serializado, nunca raw
    # Para interactive
    interactive_type: str | None = None  # button, list, flow, cta_url, location_request_message
    interactive_button_id: str | None = None
    interactive_list_id: str | None = None
    interactive_cta_url: str | None = None
    # Para reaction
    reaction_message_id: str | None = None
    reaction_emoji: str | None = None
    # Raw payload reference (GCS path se houver)
    payload_ref: str | None = None


class WebhookProcessingSummary(BaseModel):
    """Resumo do processamento do webhook (sem PII).

    Fornecido ao cliente HTTP sem expor detalhes internos.
    """

    total_received: int = 0
    total_deduped: int = 0
    total_processed: int = 0
    signature_validated: bool = False
    signature_skipped: bool = False
    errors: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class InboundMessageEvent(BaseModel):
    """Evento inbound completo com contexto processado."""

    message: NormalizedWhatsAppMessage
    received_at_unix: int
    is_resend: bool = False  # True se dedupe detectou retry


class OutboundMessageRequest(BaseModel):
    """Requisição para enviar uma mensagem outbound."""

    to: str  # Phone number E.164
    message_type: str  # Tipo técnico (text, image, etc.)
    text: str | None = None
    media_id: str | None = None  # Media ID previamente hospedado
    media_url: str | None = None  # URL público para upload
    media_filename: str | None = None
    media_mime_type: str | None = None  # MIME type para validação
    # Para location
    location_latitude: float | None = None
    location_longitude: float | None = None
    location_name: str | None = None
    location_address: str | None = None
    # Para address
    address_street: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip_code: str | None = None
    address_country_code: str | None = None
    # Para interactive
    buttons: list[dict[str, str]] | None = None
    interactive_type: str | None = None  # button, list, flow, cta_url, location_request_message
    flow_id: str | None = None  # Para flow
    flow_token: str | None = None  # Para flow
    flow_message_version: str | None = None  # Para flow
    flow_cta: str | None = None  # Para flow
    flow_action: str | None = None  # Para flow
    cta_url: str | None = None  # Para cta_url
    cta_display_text: str | None = None  # Para cta_url
    location_request_text: str | None = None  # Para location_request_message
    footer: str | None = None  # Footer para interativas
    # Para template
    template_name: str | None = None  # Para template messages
    template_params: dict[str, Any] | None = None
    # Metadata
    category: str | None = None  # MARKETING, UTILITY, AUTHENTICATION, SERVICE
    idempotency_key: str | None = None  # Para idempotência


class OutboundMessageResponse(BaseModel):
    """Resposta do envio outbound."""

    success: bool
    message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    sent_at_unix: int | None = None
