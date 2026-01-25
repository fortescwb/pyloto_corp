"""Upload de mídia para GCS com deduplicação.

Responsabilidades:
- Upload de arquivo para bucket GCS
- Registro de metadados
- Deduplicação por hash
- Retry em falhas transitórias

Conforme regras_e_padroes.md (SRP, <200 linhas, <50/função).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

from pyloto_corp.adapters.whatsapp.media_helpers import (
    ALL_SUPPORTED_MIME_TYPES,
    MediaValidationError,  # noqa: F401 - reexportado para consumidores e testes
    compute_sha256,
    generate_gcs_path,
    validate_content,
)
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from google.cloud import storage

    from pyloto_corp.adapters.whatsapp.http_client import WhatsAppHttpClient

logger: logging.Logger = get_logger(__name__)
__all__ = [
    "MediaUploader",
    "MediaUploaderError",
    "MediaMetadataStore",
    "MediaUploadResult",
    "ALL_SUPPORTED_MIME_TYPES",
]


@dataclass(frozen=True)
class MediaUploadResult:
    """Resultado de upload de mídia."""

    media_id: str | None
    gcs_uri: str
    sha256_hash: str
    size_bytes: int
    mime_type: str
    was_deduplicated: bool
    uploaded_at: datetime


class MediaMetadataStore(Protocol):
    """Contrato para persistência de metadados de mídia."""

    def get_by_hash(self, sha256_hash: str) -> MediaUploadResult | None:
        """Busca mídia por hash SHA256."""
        ...

    def save(self, result: MediaUploadResult) -> None:
        """Persiste metadados de mídia."""
        ...


class MediaUploaderError(Exception):
    """Erro genérico de upload de mídia."""

    pass


class MediaUploader:
    """Gerencia upload de mídia para GCS com deduplicação."""

    def __init__(
        self,
        gcs_client: storage.Client,
        bucket_name: str,
        metadata_store: MediaMetadataStore,
        whatsapp_client: WhatsAppHttpClient | None = None,
    ) -> None:
        """Inicializa uploader.

        Args:
            gcs_client: Cliente Google Cloud Storage
            bucket_name: Nome do bucket GCS
            metadata_store: Store para metadados
            whatsapp_client: Cliente WhatsApp API (opcional)
        """
        self._gcs = gcs_client
        self._bucket_name = bucket_name
        self._metadata_store = metadata_store
        self._whatsapp_client = whatsapp_client

    async def upload(
        self,
        content: bytes,
        mime_type: str,
        user_key: str,
        upload_to_whatsapp: bool = False,
    ) -> MediaUploadResult:
        """Faz upload de mídia com deduplicação.

        Args:
            content: Bytes do arquivo
            mime_type: Tipo MIME
            user_key: Chave do usuário
            upload_to_whatsapp: Se True, também faz upload para WhatsApp

        Returns:
            MediaUploadResult

        Raises:
            MediaValidationError: Se conteúdo inválido
            MediaUploaderError: Se falha no upload
        """
        validate_content(content, mime_type)
        sha256_hash = compute_sha256(content)

        existing = self._metadata_store.get_by_hash(sha256_hash)
        if existing:
            logger.info("Mídia duplicada (dedup hit)")
            return existing

        gcs_uri = await self._upload_to_gcs(content, mime_type, user_key, sha256_hash)
        media_id = None
        if upload_to_whatsapp and self._whatsapp_client:
            media_id = await self._upload_to_whatsapp(content, mime_type)

        result = MediaUploadResult(
            media_id=media_id,
            gcs_uri=gcs_uri,
            sha256_hash=sha256_hash,
            size_bytes=len(content),
            mime_type=mime_type,
            was_deduplicated=False,
            uploaded_at=datetime.now(tz=UTC),
        )

        self._metadata_store.save(result)

        logger.info(
            "Mídia uploaded com sucesso",
            extra={"hash_prefix": sha256_hash[:12], "size_bytes": len(content)},
        )

        return result

    async def _upload_to_gcs(
        self,
        content: bytes,
        mime_type: str,
        user_key: str,
        sha256_hash: str,
    ) -> str:
        """Upload para GCS."""
        path = generate_gcs_path(user_key, sha256_hash, mime_type)

        try:
            bucket = self._gcs.bucket(self._bucket_name)
            blob = bucket.blob(path)
            blob.upload_from_string(content, content_type=mime_type)
            gcs_uri = f"gs://{self._bucket_name}/{path}"
            logger.debug("Upload GCS concluído")
            return gcs_uri
        except Exception as e:
            logger.error("Falha no upload GCS", extra={"error": str(e)})
            raise MediaUploaderError(f"Falha no upload GCS: {e}") from e

    async def _upload_to_whatsapp(
        self,
        content: bytes,
        mime_type: str,
    ) -> str | None:
        """Upload para WhatsApp Media API (placeholder)."""
        logger.debug("Upload WhatsApp API pendente")
        return None

    async def delete(self, gcs_uri: str) -> bool:
        """Remove mídia do GCS.

        Args:
            gcs_uri: URI completa (gs://bucket/path)

        Returns:
            True se removido, False se não existia
        """
        if not gcs_uri.startswith(f"gs://{self._bucket_name}/"):
            logger.warning("Tentativa de deletar mídia de bucket incorreto")
            return False

        path = gcs_uri.replace(f"gs://{self._bucket_name}/", "")

        try:
            bucket = self._gcs.bucket(self._bucket_name)
            blob = bucket.blob(path)
            blob.delete()
            logger.info("Mídia removida do GCS")
            return True
        except Exception:
            logger.warning("Falha ao remover mídia do GCS")
            return False
