"""Exportador para GCS — URLs assinadas e cleanup.

Responsabilidades:
- Salvar exports em bucket GCS (não público)
- Gerar URLs assinadas com expiração configurável
- Registrar metadados em Firestore (opcional)
- Cleanup de exports antigos (retention policy)

Conforme regras_e_padroes.md (sem PII em logs, auditabilidade).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from google.cloud import storage

from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    pass

logger: logging.Logger = get_logger(__name__)

# Configurações padrão
DEFAULT_SIGNED_URL_EXPIRATION_DAYS = 7
DEFAULT_RETENTION_DAYS = 180


@dataclass(slots=True, frozen=True)
class ExportMetadata:
    """Metadados de uma exportação."""

    gcs_uri: str
    signed_url: str | None
    user_key: str
    created_at: datetime
    expires_at: datetime | None
    size_bytes: int
    content_type: str


class GCSHistoryExporter:
    """Persiste exports em bucket GCS com URLs assinadas.

    Características:
    - Upload para bucket privado
    - Geração de URL assinada com expiração
    - Registro de metadados em Firestore (opcional)
    - Cleanup de exports antigos
    """

    def __init__(
        self,
        bucket_name: str,
        client: storage.Client | None = None,
        firestore_client: Any | None = None,
        metadata_collection: str = "exports",
    ) -> None:
        """Inicializa exportador.

        Args:
            bucket_name: Nome do bucket GCS
            client: Cliente GCS (cria novo se não fornecido)
            firestore_client: Cliente Firestore para metadados (opcional)
            metadata_collection: Nome da collection de metadados
        """
        self._bucket_name = bucket_name
        self._client = client or storage.Client()
        self._firestore = firestore_client
        self._metadata_collection = metadata_collection

    def save(
        self,
        *,
        user_key: str,
        content: bytes,
        content_type: str = "text/plain",
    ) -> str:
        """Salva export em GCS.

        Args:
            user_key: Chave do usuário (para organização)
            content: Conteúdo do export
            content_type: Tipo MIME do conteúdo

        Returns:
            URI GCS (gs://bucket/path)
        """
        now = datetime.now(tz=UTC)
        object_name = self._generate_object_name(user_key, now)

        bucket = self._client.bucket(self._bucket_name)
        blob = bucket.blob(object_name)
        blob.upload_from_string(content, content_type=content_type)

        gcs_uri = f"gs://{self._bucket_name}/{object_name}"

        logger.info(
            "Export saved to GCS",
            extra={
                "user_key_prefix": user_key[:8] + "...",
                "size_bytes": len(content),
            },
        )

        return gcs_uri

    def save_with_metadata(
        self,
        *,
        user_key: str,
        content: bytes,
        content_type: str = "text/plain",
        signed_url_expiration_days: int = DEFAULT_SIGNED_URL_EXPIRATION_DAYS,
    ) -> ExportMetadata:
        """Salva export com metadados e URL assinada.

        Args:
            user_key: Chave do usuário
            content: Conteúdo do export
            content_type: Tipo MIME
            signed_url_expiration_days: Dias de validade da URL

        Returns:
            ExportMetadata com todos os detalhes
        """
        now = datetime.now(tz=UTC)
        object_name = self._generate_object_name(user_key, now)
        gcs_uri = self._upload_bytes(object_name, content, content_type)
        signed_url, expires_at = self._generate_signed_url_with_expiry(
            object_name, signed_url_expiration_days, now
        )
        metadata = self._build_export_metadata(
            gcs_uri, signed_url, user_key, now, expires_at, len(content), content_type
        )
        self._persist_metadata(metadata)
        self._log_saved_with_url(user_key, len(content), signed_url_expiration_days)
        return metadata

    def _upload_bytes(self, object_name: str, content: bytes, content_type: str) -> str:
        """Realiza upload para GCS e retorna URI."""
        bucket = self._client.bucket(self._bucket_name)
        blob = bucket.blob(object_name)
        blob.upload_from_string(content, content_type=content_type)
        return f"gs://{self._bucket_name}/{object_name}"

    def _generate_signed_url_with_expiry(
        self, object_name: str, expiration_days: int, now: datetime
    ) -> tuple[str, datetime]:
        """Gera URL assinada com data de expiração calculada."""
        expires_at = now + timedelta(days=expiration_days)
        signed_url = self.generate_signed_url(object_name, expiration_days)
        return signed_url, expires_at

    def _build_export_metadata(
        self,
        gcs_uri: str,
        signed_url: str,
        user_key: str,
        created_at: datetime,
        expires_at: datetime,
        size_bytes: int,
        content_type: str,
    ) -> ExportMetadata:
        """Cria dataclass de metadados do export."""
        return ExportMetadata(
            gcs_uri=gcs_uri,
            signed_url=signed_url,
            user_key=user_key,
            created_at=created_at,
            expires_at=expires_at,
            size_bytes=size_bytes,
            content_type=content_type,
        )

    def _persist_metadata(self, metadata: ExportMetadata) -> None:
        """Persiste metadados no Firestore quando configurado."""
        if self._firestore:
            self._save_metadata_to_firestore(metadata)

    def _log_saved_with_url(
        self, user_key: str, size_bytes: int, signed_url_expiration_days: int
    ) -> None:
        """Registra log estruturado do salvamento com URL assinada."""
        logger.info(
            "Export saved with signed URL",
            extra={
                "user_key_prefix": user_key[:8] + "...",
                "size_bytes": size_bytes,
                "expires_days": signed_url_expiration_days,
            },
        )

    def generate_signed_url(
        self,
        object_name: str,
        expiration_days: int = DEFAULT_SIGNED_URL_EXPIRATION_DAYS,
    ) -> str:
        """Gera URL assinada para objeto existente.

        Args:
            object_name: Nome do objeto no bucket
            expiration_days: Dias de validade

        Returns:
            URL assinada para acesso temporário
        """
        bucket = self._client.bucket(self._bucket_name)
        blob = bucket.blob(object_name)

        expiration = timedelta(days=expiration_days)

        url = blob.generate_signed_url(
            version="v4",
            expiration=expiration,
            method="GET",
        )

        logger.debug(
            "Signed URL generated",
            extra={"object_prefix": object_name[:20] + "..."},
        )

        return url

    def cleanup_old_exports(
        self,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ) -> int:
        """Remove exports mais antigos que retention_days.

        Args:
            retention_days: Dias de retenção

        Returns:
            Número de objetos removidos
        """
        bucket = self._client.bucket(self._bucket_name)
        prefix = "exports/conversations/"
        cutoff = datetime.now(tz=UTC) - timedelta(days=retention_days)

        deleted_count = 0

        for blob in bucket.list_blobs(prefix=prefix):
            if blob.time_created and blob.time_created < cutoff:
                blob.delete()
                deleted_count += 1
                logger.debug(
                    "Old export deleted",
                    extra={"object_prefix": blob.name[:20] + "..."},
                )

        if deleted_count > 0:
            logger.info(
                "Cleanup completed",
                extra={
                    "deleted_count": deleted_count,
                    "retention_days": retention_days,
                },
            )

        # Limpar metadados do Firestore
        if self._firestore:
            self._cleanup_firestore_metadata(cutoff)

        return deleted_count

    def _generate_object_name(self, user_key: str, timestamp: datetime) -> str:
        """Gera nome do objeto com estrutura organizada."""
        date_path = timestamp.strftime("%Y/%m/%d")
        filename = f"{timestamp.strftime('%H%M%S')}_{user_key[:16]}_history.txt"
        return f"exports/conversations/{date_path}/{filename}"

    def _save_metadata_to_firestore(self, metadata: ExportMetadata) -> None:
        """Salva metadados do export em Firestore."""
        if not self._firestore:
            return

        try:
            doc_id = f"{metadata.user_key}_{metadata.created_at.strftime('%Y%m%d%H%M%S')}"
            doc_ref = self._firestore.collection(self._metadata_collection).document(doc_id)

            doc_ref.set(
                {
                    "gcs_uri": metadata.gcs_uri,
                    "user_key": metadata.user_key,
                    "created_at": metadata.created_at,
                    "expires_at": metadata.expires_at,
                    "size_bytes": metadata.size_bytes,
                    "content_type": metadata.content_type,
                    # Não salvar signed_url (pode expirar)
                }
            )

            logger.debug(
                "Export metadata saved to Firestore",
                extra={"doc_id_prefix": doc_id[:16] + "..."},
            )

        except Exception as e:
            # Não falhar o export por erro de metadados
            logger.warning(
                "Failed to save export metadata",
                extra={"error": str(e)},
            )

    def _cleanup_firestore_metadata(self, cutoff: datetime) -> None:
        """Remove metadados antigos do Firestore."""
        if not self._firestore:
            return

        try:
            query = (
                self._firestore.collection(self._metadata_collection)
                .where("created_at", "<", cutoff)
                .limit(500)  # Batch para evitar timeout
            )

            deleted = 0
            for doc in query.stream():
                doc.reference.delete()
                deleted += 1

            if deleted > 0:
                logger.debug(
                    "Firestore metadata cleaned up",
                    extra={"deleted_count": deleted},
                )

        except Exception as e:
            logger.warning(
                "Failed to cleanup Firestore metadata",
                extra={"error": str(e)},
            )


def create_gcs_exporter(
    bucket_name: str,
    firestore_client: Any | None = None,
) -> GCSHistoryExporter:
    """Factory para GCSHistoryExporter.

    Args:
        bucket_name: Nome do bucket GCS
        firestore_client: Cliente Firestore para metadados (opcional)

    Returns:
        GCSHistoryExporter configurado
    """
    return GCSHistoryExporter(
        bucket_name=bucket_name,
        firestore_client=firestore_client,
    )
