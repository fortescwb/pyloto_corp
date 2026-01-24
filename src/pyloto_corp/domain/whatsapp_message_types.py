"""Modelos estruturados para tipos de mensagens Meta/WhatsApp.

Responsabilidade:
- Definir estruturas pydantic para cada tipo de conteúdo suportado
- Garantir conformidade com API Meta/WhatsApp
- Fornecer validadores específicos por tipo
- Facilitar serialização e desserialização
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TextMessage(BaseModel):
    """Mensagem de texto simples ou com links."""

    body: str = Field(..., min_length=1, max_length=4096)
    preview_url: bool = False


class ImageMessage(BaseModel):
    """Mensagem com imagem (JPG, PNG)."""

    id: str | None = None  # Media ID (inbound)
    url: str | None = None  # URL pública (outbound)
    caption: str | None = Field(None, max_length=1024)

    @field_validator("id", "url", mode="before")
    @classmethod
    def require_id_or_url(cls, v: Any) -> Any:
        """Garante que ID (inbound) ou URL (outbound) esteja presente."""
        return v

    def model_post_init(self, __context: Any) -> None:
        """Valida que id ou url é fornecido."""
        if not self.id and not self.url:
            raise ValueError(
                "Image must have 'id' (inbound) or 'url' (outbound)"
            )


class VideoMessage(BaseModel):
    """Mensagem com vídeo (MP4, 3GPP)."""

    id: str | None = None  # Media ID (inbound)
    url: str | None = None  # URL pública (outbound)
    caption: str | None = Field(None, max_length=1024)

    def model_post_init(self, __context: Any) -> None:
        """Valida que id ou url é fornecido."""
        if not self.id and not self.url:
            raise ValueError(
                "Video must have 'id' (inbound) or 'url' (outbound)"
            )


class AudioMessage(BaseModel):
    """Mensagem com áudio ou nota de voz (AAC, MP4, AMR, OGG)."""

    id: str | None = None  # Media ID (inbound)
    url: str | None = None  # URL pública (outbound)

    def model_post_init(self, __context: Any) -> None:
        """Valida que id ou url é fornecido."""
        if not self.id and not self.url:
            raise ValueError(
                "Audio must have 'id' (inbound) or 'url' (outbound)"
            )


class DocumentMessage(BaseModel):
    """Mensagem com documento (PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX)."""

    id: str | None = None  # Media ID (inbound)
    url: str | None = None  # URL pública (outbound)
    filename: str | None = Field(None, max_length=240)
    caption: str | None = Field(None, max_length=1024)

    def model_post_init(self, __context: Any) -> None:
        """Valida que id ou url é fornecido."""
        if not self.id and not self.url:
            raise ValueError(
                "Document must have 'id' (inbound) or 'url' (outbound)"
            )


class StickerMessage(BaseModel):
    """Mensagem com adesivo."""

    id: str | None = None  # Media ID (inbound)
    url: str | None = None  # URL pública (outbound)

    def model_post_init(self, __context: Any) -> None:
        """Valida que id ou url é fornecido."""
        if not self.id and not self.url:
            raise ValueError(
                "Sticker must have 'id' (inbound) or 'url' (outbound)"
            )


class LocationMessage(BaseModel):
    """Mensagem de localização (coordenadas geográficas estáticas)."""

    latitude: float
    longitude: float
    name: str | None = None  # Nome da localização
    address: str | None = None  # Endereço


class ContactMessage(BaseModel):
    """Mensagem com cartão de contato (vCard)."""

    name: str = Field(..., min_length=1, max_length=1024)
    phones: list[str] | None = None
    emails: list[str] | None = None
    urls: list[str] | None = None
    organization: str | None = None


class AddressMessage(BaseModel):
    """Mensagem de endereço (pedido de endereço de entrega)."""

    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country_code: str | None = None
    country: str | None = None
    notes: str | None = Field(None, max_length=1024)  # Instruções adicionais


class TemplateMessage(BaseModel):
    """Mensagem de template (modelo).
    
    Templates são mensagens pré-aprovadas pela Meta para:
    - Marketing
    - Utility (notificações)
    - Authentication (OTP)
    
    Não requerem janela de 24h aberta.
    """

    namespace: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=512)
    language: str = "pt_BR"  # Código de idioma
    parameters: dict[str, str | int | float] | None = None  # Parâmetros variáveis
    category: str | None = None  # MARKETING, UTILITY, AUTHENTICATION


@dataclass(slots=True)
class ButtonReply:
    """Botão de resposta rápida para mensagem interativa."""

    id: str  # ID único do botão
    title: str  # Texto exibido


@dataclass(slots=True)
class ListItem:
    """Item de lista para mensagem interativa."""

    id: str  # ID único do item
    title: str  # Título do item
    description: str | None = None  # Descrição opcional


class InteractiveButtonMessage(BaseModel):
    """Mensagem interativa com botões de resposta rápida."""

    body: str = Field(..., min_length=1, max_length=1024)
    buttons: list[ButtonReply] = Field(..., min_items=1, max_items=3)
    footer: str | None = Field(None, max_length=60)


class InteractiveListMessage(BaseModel):
    """Mensagem interativa com lista de opções."""

    body: str = Field(..., min_length=1, max_length=1024)
    button: str = Field(..., max_length=20)  # Texto do botão "Ver opções"
    sections: list[dict[str, Any]] = Field(..., min_items=1, max_items=10)
    footer: str | None = Field(None, max_length=60)


class InteractiveFlowMessage(BaseModel):
    """Mensagem interativa com formulário (WhatsApp Flow)."""

    flow_message_version: str  # Versão do schema do Flow (ex.: "3")
    flow_token: str  # Token fornecido pelo backend do Flow
    flow_id: str
    flow_cta: str = Field(..., max_length=20)  # Texto do botão
    flow_action: str  # Ex.: "navigate"
    body: str | None = Field(None, max_length=1024)
    footer: str | None = Field(None, max_length=60)


class InteractiveCTAURLMessage(BaseModel):
    """Mensagem interativa com botão de URL (CTA = Call To Action).
    
    Associa uma URL a um botão, permitindo URLs longas sem obscurecer o corpo.
    """

    body: str = Field(..., min_length=1, max_length=1024)
    cta_url: str = Field(..., min_length=1)  # URL completa
    cta_display_text: str = Field(..., max_length=20)  # Texto do botão
    footer: str | None = Field(None, max_length=60)


class InteractiveLocationRequestMessage(BaseModel):
    """Mensagem interativa com botão de envio de localização.
    
    Exibe corpo de texto e botão para compartilhar localização.
    """

    body: str = Field(..., min_length=1, max_length=1024)
    footer: str | None = Field(None, max_length=60)


class ReactionMessage(BaseModel):
    """Reação (emoji) a mensagem específica."""

    message_id: str  # ID da mensagem sendo reagida
    emoji: str = Field(..., min_length=1, max_length=2)


@dataclass(slots=True)
class MessageMetadata:
    """Metadados de uma mensagem de qualquer tipo."""

    message_id: str
    timestamp: int
    from_number: str
    message_type: str
    category: str | None = None  # Categoria (MARKETING, UTILITY, etc.)
    media_url: str | None = None  # URL da mídia se houver
    media_type: str | None = None  # MIME type
