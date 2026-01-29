"""Testes unitários para MediaUploader.

Cobertura >90% conforme regras_e_padroes.md:
- Cenários de sucesso (upload, dedup)
- Erros de validação (tamanho, tipo)
- Falhas de GCS
- Edge cases
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from pyloto_corp.adapters.whatsapp.media_helpers import (
    ALL_SUPPORTED_MIME_TYPES,
    MediaValidationError,
    compute_sha256,
    generate_gcs_path,
    validate_content,
)
from pyloto_corp.adapters.whatsapp.media_uploader import (
    MediaMetadataStore,
    MediaUploader,
    MediaUploaderError,
    MediaUploadResult,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_gcs_client() -> MagicMock:
    """Mock de cliente GCS."""
    client = MagicMock()
    bucket = MagicMock()
    blob = MagicMock()

    client.bucket.return_value = bucket
    bucket.blob.return_value = blob
    blob.upload_from_string = MagicMock()
    blob.delete = MagicMock()

    return client


@pytest.fixture
def mock_metadata_store() -> MagicMock:
    """Mock de MediaMetadataStore."""
    store = MagicMock(spec=MediaMetadataStore)
    store.get_by_hash.return_value = None
    store.save = MagicMock()
    return store


@pytest.fixture
def sample_image_content() -> bytes:
    """Conteúdo de imagem de teste (pequeno)."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


@pytest.fixture
def sample_upload_result() -> MediaUploadResult:
    """Resultado de upload para testes de dedup."""
    return MediaUploadResult(
        media_id="existing_media_id",
        gcs_uri="gs://test-bucket/media/2026/01/25/user123/abc123.png",
        sha256_hash="abc123def456" * 5,
        size_bytes=1000,
        mime_type="image/png",
        was_deduplicated=True,
        uploaded_at=datetime.now(tz=UTC),
    )


# =============================================================================
# Testes: compute_sha256
# =============================================================================


class TestComputeSha256:
    """Testes para função de hash SHA256."""

    def test_hash_consistent_for_same_content(self) -> None:
        """Mesmo conteúdo produz mesmo hash."""
        content = b"test content"
        hash1 = compute_sha256(content)
        hash2 = compute_sha256(content)
        assert hash1 == hash2

    def test_hash_differs_for_different_content(self) -> None:
        """Conteúdos diferentes produzem hashes diferentes."""
        hash1 = compute_sha256(b"content A")
        hash2 = compute_sha256(b"content B")
        assert hash1 != hash2

    def test_hash_is_64_hex_chars(self) -> None:
        """Hash SHA256 tem 64 caracteres hexadecimais."""
        hash_value = compute_sha256(b"test")
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)


# =============================================================================
# Testes: validate_content
# =============================================================================


class TestValidateContent:
    """Testes para validação de conteúdo."""

    def test_valid_image_passes(self) -> None:
        """Imagem válida passa validação."""
        content = b"\x89PNG" + b"\x00" * 100
        validate_content(content, "image/jpeg")  # Não deve lançar exceção

    def test_valid_video_passes(self) -> None:
        """Vídeo válido passa validação."""
        content = b"\x00" * 1000
        validate_content(content, "video/mp4")

    def test_valid_audio_passes(self) -> None:
        """Áudio válido passa validação."""
        content = b"\x00" * 500
        validate_content(content, "audio/aac")

    def test_valid_document_passes(self) -> None:
        """Documento válido passa validação."""
        content = b"%PDF-1.4" + b"\x00" * 200
        validate_content(content, "application/pdf")

    def test_empty_content_raises(self) -> None:
        """Conteúdo vazio lança exceção."""
        with pytest.raises(MediaValidationError, match="vazio"):
            validate_content(b"", "image/jpeg")

    def test_oversized_content_raises(self) -> None:
        """Conteúdo acima do limite lança exceção."""
        content = b"\x00" * (2 * 1024 * 1024)  # 2MB
        with pytest.raises(MediaValidationError, match="excede limite"):
            validate_content(content, "image/jpeg", max_size_mb=1)

    def test_unsupported_mime_type_raises(self) -> None:
        """Tipo MIME não suportado lança exceção."""
        with pytest.raises(MediaValidationError, match="não suportado"):
            validate_content(b"content", "application/x-unknown")

    def test_all_supported_types_pass(self) -> None:
        """Todos os tipos suportados passam validação."""
        content = b"\x00" * 100
        for mime_type in ALL_SUPPORTED_MIME_TYPES:
            validate_content(content, mime_type)  # Não deve lançar


# =============================================================================
# Testes: generate_gcs_path
# =============================================================================


class TestGenerateGcsPath:
    """Testes para geração de path GCS."""

    def test_path_contains_user_key(self) -> None:
        """Path contém prefixo do user_key."""
        path = generate_gcs_path("user123", "abc123def", "image/jpeg")
        assert "user123" in path

    def test_path_contains_hash_prefix(self) -> None:
        """Path contém prefixo do hash."""
        path = generate_gcs_path("user123", "abc123def456", "image/jpeg")
        assert "abc123def456" in path

    def test_path_has_correct_extension(self) -> None:
        """Path tem extensão correta baseada em MIME."""
        path_jpeg = generate_gcs_path("user", "hash", "image/jpeg")
        path_pdf = generate_gcs_path("user", "hash", "application/pdf")

        assert path_jpeg.endswith(".jpeg")
        assert path_pdf.endswith(".pdf")

    def test_path_starts_with_media(self) -> None:
        """Path começa com 'media/'."""
        path = generate_gcs_path("user", "hash", "image/png")
        assert path.startswith("media/")


# =============================================================================
# Testes: MediaUploader.upload
# =============================================================================


class TestMediaUploaderUpload:
    """Testes para upload de mídia."""

    @pytest.mark.asyncio
    async def test_upload_success(
        self,
        mock_gcs_client: MagicMock,
        mock_metadata_store: MagicMock,
        sample_image_content: bytes,
    ) -> None:
        """Upload bem-sucedido retorna resultado correto."""
        uploader = MediaUploader(
            gcs_client=mock_gcs_client,
            bucket_name="test-bucket",
            metadata_store=mock_metadata_store,
        )

        result = await uploader.upload(
            content=sample_image_content,
            mime_type="image/png",
            user_key="user123",
        )

        assert result.gcs_uri.startswith("gs://test-bucket/")
        assert result.sha256_hash is not None
        assert result.size_bytes == len(sample_image_content)
        assert result.mime_type == "image/png"
        assert result.was_deduplicated is False

    @pytest.mark.asyncio
    async def test_upload_with_deduplication(
        self,
        mock_gcs_client: MagicMock,
        mock_metadata_store: MagicMock,
        sample_image_content: bytes,
        sample_upload_result: MediaUploadResult,
    ) -> None:
        """Upload duplicado retorna resultado existente."""
        mock_metadata_store.get_by_hash.return_value = sample_upload_result

        uploader = MediaUploader(
            gcs_client=mock_gcs_client,
            bucket_name="test-bucket",
            metadata_store=mock_metadata_store,
        )

        result = await uploader.upload(
            content=sample_image_content,
            mime_type="image/png",
            user_key="user123",
        )

        # Deve retornar o existente
        assert result == sample_upload_result
        # Não deve fazer upload para GCS
        mock_gcs_client.bucket.return_value.blob.return_value.upload_from_string.assert_not_called()

    @pytest.mark.asyncio
    async def test_upload_validates_content(
        self,
        mock_gcs_client: MagicMock,
        mock_metadata_store: MagicMock,
    ) -> None:
        """Upload valida conteúdo antes de processar."""
        uploader = MediaUploader(
            gcs_client=mock_gcs_client,
            bucket_name="test-bucket",
            metadata_store=mock_metadata_store,
        )

        with pytest.raises(MediaValidationError):
            await uploader.upload(
                content=b"",  # Conteúdo vazio
                mime_type="image/png",
                user_key="user123",
            )

    @pytest.mark.asyncio
    async def test_upload_gcs_failure_raises(
        self,
        mock_gcs_client: MagicMock,
        mock_metadata_store: MagicMock,
        sample_image_content: bytes,
    ) -> None:
        """Falha no GCS lança MediaUploaderError."""
        (mock_gcs_client.bucket.return_value.blob.return_value
            .upload_from_string.side_effect) = Exception(
            "GCS error"
        )

        uploader = MediaUploader(
            gcs_client=mock_gcs_client,
            bucket_name="test-bucket",
            metadata_store=mock_metadata_store,
        )

        with pytest.raises(MediaUploaderError, match="GCS"):
            await uploader.upload(
                content=sample_image_content,
                mime_type="image/png",
                user_key="user123",
            )

    @pytest.mark.asyncio
    async def test_upload_saves_metadata(
        self,
        mock_gcs_client: MagicMock,
        mock_metadata_store: MagicMock,
        sample_image_content: bytes,
    ) -> None:
        """Upload persiste metadados no store."""
        uploader = MediaUploader(
            gcs_client=mock_gcs_client,
            bucket_name="test-bucket",
            metadata_store=mock_metadata_store,
        )

        await uploader.upload(
            content=sample_image_content,
            mime_type="image/png",
            user_key="user123",
        )

        mock_metadata_store.save.assert_called_once()


# =============================================================================
# Testes: MediaUploader.delete
# =============================================================================


class TestMediaUploaderDelete:
    """Testes para remoção de mídia."""

    @pytest.mark.asyncio
    async def test_delete_success(
        self,
        mock_gcs_client: MagicMock,
        mock_metadata_store: MagicMock,
    ) -> None:
        """Delete bem-sucedido retorna True."""
        uploader = MediaUploader(
            gcs_client=mock_gcs_client,
            bucket_name="test-bucket",
            metadata_store=mock_metadata_store,
        )

        result = await uploader.delete("gs://test-bucket/media/path/file.png")

        assert result is True
        mock_gcs_client.bucket.return_value.blob.return_value.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_wrong_bucket_returns_false(
        self,
        mock_gcs_client: MagicMock,
        mock_metadata_store: MagicMock,
    ) -> None:
        """Delete de bucket errado retorna False."""
        uploader = MediaUploader(
            gcs_client=mock_gcs_client,
            bucket_name="test-bucket",
            metadata_store=mock_metadata_store,
        )

        result = await uploader.delete("gs://other-bucket/media/path/file.png")

        assert result is False
        mock_gcs_client.bucket.return_value.blob.return_value.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_gcs_failure_returns_false(
        self,
        mock_gcs_client: MagicMock,
        mock_metadata_store: MagicMock,
    ) -> None:
        """Falha no GCS retorna False sem lançar exceção."""
        mock_gcs_client.bucket.return_value.blob.return_value.delete.side_effect = Exception(
            "Not found"
        )

        uploader = MediaUploader(
            gcs_client=mock_gcs_client,
            bucket_name="test-bucket",
            metadata_store=mock_metadata_store,
        )

        result = await uploader.delete("gs://test-bucket/media/path/file.png")

        assert result is False


# =============================================================================
# Testes: Edge Cases
# =============================================================================


class TestMediaUploaderEdgeCases:
    """Testes para casos de borda."""

    @pytest.mark.asyncio
    async def test_large_file_at_limit(
        self,
        mock_gcs_client: MagicMock,
        mock_metadata_store: MagicMock,
    ) -> None:
        """Arquivo exatamente no limite de tamanho passa."""
        # 100MB - 1 byte (abaixo do limite de 100MB)
        content = b"\x00" * (100 * 1024 * 1024 - 1)

        uploader = MediaUploader(
            gcs_client=mock_gcs_client,
            bucket_name="test-bucket",
            metadata_store=mock_metadata_store,
        )

        result = await uploader.upload(
            content=content,
            mime_type="application/pdf",
            user_key="user123",
        )

        assert result.size_bytes == len(content)

    @pytest.mark.asyncio
    async def test_unicode_user_key(
        self,
        mock_gcs_client: MagicMock,
        mock_metadata_store: MagicMock,
        sample_image_content: bytes,
    ) -> None:
        """User key com caracteres especiais funciona."""
        uploader = MediaUploader(
            gcs_client=mock_gcs_client,
            bucket_name="test-bucket",
            metadata_store=mock_metadata_store,
        )

        # User key com acentos (normalizado via hash)
        result = await uploader.upload(
            content=sample_image_content,
            mime_type="image/jpeg",
            user_key="usuário_测试",
        )

        assert result.gcs_uri is not None

    @pytest.mark.asyncio
    async def test_all_video_types(
        self,
        mock_gcs_client: MagicMock,
        mock_metadata_store: MagicMock,
    ) -> None:
        """Todos os tipos de vídeo suportados funcionam."""
        uploader = MediaUploader(
            gcs_client=mock_gcs_client,
            bucket_name="test-bucket",
            metadata_store=mock_metadata_store,
        )

        for mime_type in ["video/mp4", "video/3gpp"]:
            result = await uploader.upload(
                content=b"\x00" * 100,
                mime_type=mime_type,
                user_key="user123",
            )
            assert result.mime_type == mime_type
