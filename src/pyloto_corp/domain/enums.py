"""Enums de domínio para intenções, outcomes e tipos de mensagens Meta/WhatsApp."""

from __future__ import annotations

from enum import StrEnum


class Outcome(StrEnum):
    """Outcomes terminais canônicos."""

    HANDOFF_HUMAN = "HANDOFF_HUMAN"
    SELF_SERVE_INFO = "SELF_SERVE_INFO"
    ROUTE_EXTERNAL = "ROUTE_EXTERNAL"
    SCHEDULED_FOLLOWUP = "SCHEDULED_FOLLOWUP"
    AWAITING_USER = "AWAITING_USER"
    DUPLICATE_OR_SPAM = "DUPLICATE_OR_SPAM"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED_INTERNAL = "FAILED_INTERNAL"


class Intent(StrEnum):
    """Intenções principais possíveis na sessão."""

    ENTRY_UNKNOWN = "ENTRY_UNKNOWN"
    CUSTOM_SOFTWARE = "CUSTOM_SOFTWARE"
    SAAS_COMMUNICATION = "SAAS_COMMUNICATION"
    PYLOTO_ENTREGA_REQUEST = "PYLOTO_ENTREGA_REQUEST"
    PYLOTO_ENTREGA_DRIVER_SIGNUP = "PYLOTO_ENTREGA_DRIVER_SIGNUP"
    PYLOTO_ENTREGA_MERCHANT_SIGNUP = "PYLOTO_ENTREGA_MERCHANT_SIGNUP"
    INSTITUTIONAL = "INSTITUTIONAL"
    UNSUPPORTED = "UNSUPPORTED"


class MessageType(StrEnum):
    """Tipos de conteúdo suportados pela API Meta/WhatsApp.

    Cobre todos os 16 tipos documentados pela Meta:
    - text, image, video, audio, document, sticker
    - location, contacts, address
    - interactive (com subtipo: button, list, flow, cta_url, location_request_message)
    - template
    - reaction
    """

    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    STICKER = "sticker"
    LOCATION = "location"
    CONTACTS = "contacts"
    ADDRESS = "address"
    INTERACTIVE = "interactive"
    TEMPLATE = "template"
    REACTION = "reaction"


class InteractiveType(StrEnum):
    """Tipos de mensagens interativas suportadas.

    Conforme API Meta:
    - button: até 3 botões de resposta predefinida
    - list: lista de opções para escolha
    - flow: WhatsApp Flows (formulários estruturados)
    - cta_url: botão com URL (CTA = Call To Action)
    - location_request_message: solicitação de envio de localização
    """

    BUTTON = "button"
    LIST = "list"
    FLOW = "flow"
    CTA_URL = "cta_url"
    LOCATION_REQUEST_MESSAGE = "location_request_message"


class MessageCategory(StrEnum):
    """Categorias de mensagens conforme política de cobrança Meta/WhatsApp."""

    MARKETING = "MARKETING"
    UTILITY = "UTILITY"
    AUTHENTICATION = "AUTHENTICATION"
    SERVICE = "SERVICE"


class MediaType(StrEnum):
    """Tipos MIME suportados para mídia."""

    IMAGE_JPEG = "image/jpeg"
    IMAGE_PNG = "image/png"
    VIDEO_MP4 = "video/mp4"
    VIDEO_3GPP = "video/3gpp"
    AUDIO_AAC = "audio/aac"
    AUDIO_MP4 = "audio/mp4"
    AUDIO_AMR = "audio/amr"
    AUDIO_OGG = "audio/ogg"
    DOCUMENT_PDF = "application/pdf"
    DOCUMENT_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    DOCUMENT_DOC = "application/msword"
    DOCUMENT_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    DOCUMENT_PPT = "application/vnd.ms-powerpoint"
    DOCUMENT_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    DOCUMENT_XLS = "application/vnd.ms-excel"
