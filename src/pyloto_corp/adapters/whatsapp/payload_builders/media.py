"""Builders para mensagens de mídia (imagem, vídeo, áudio, documento)."""

from __future__ import annotations

from typing import Any

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest


def _build_media_object(
    media_id: str | None,
    media_url: str | None,
    caption: str | None = None,
) -> dict[str, Any]:
    """Constrói objeto de mídia base.

    Args:
        media_id: ID de mídia hospedada na Meta
        media_url: URL pública para upload
        caption: Legenda opcional

    Returns:
        Objeto media conforme API Meta
    """
    media_obj: dict[str, Any] = {}

    if media_id:
        media_obj["id"] = media_id
    elif media_url:
        media_obj["link"] = media_url

    if caption:
        media_obj["caption"] = caption

    return media_obj


class ImagePayloadBuilder:
    """Builder para mensagens de imagem."""

    def build(self, request: OutboundMessageRequest) -> dict[str, Any]:
        """Constrói payload para mensagem de imagem."""
        return {
            "image": _build_media_object(
                request.media_id,
                request.media_url,
                request.text,
            )
        }


class VideoPayloadBuilder:
    """Builder para mensagens de vídeo."""

    def build(self, request: OutboundMessageRequest) -> dict[str, Any]:
        """Constrói payload para mensagem de vídeo."""
        return {
            "video": _build_media_object(
                request.media_id,
                request.media_url,
                request.text,
            )
        }


class AudioPayloadBuilder:
    """Builder para mensagens de áudio."""

    def build(self, request: OutboundMessageRequest) -> dict[str, Any]:
        """Constrói payload para mensagem de áudio (sem caption)."""
        return {
            "audio": _build_media_object(
                request.media_id,
                request.media_url,
            )
        }


class DocumentPayloadBuilder:
    """Builder para mensagens de documento."""

    def build(self, request: OutboundMessageRequest) -> dict[str, Any]:
        """Constrói payload para mensagem de documento."""
        doc_obj = _build_media_object(
            request.media_id,
            request.media_url,
            request.text,
        )
        if request.media_filename:
            doc_obj["filename"] = request.media_filename
        return {"document": doc_obj}
