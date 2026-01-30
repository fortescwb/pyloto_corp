"""Testes unitários para GCSHistoryExporter — URLs assinadas e cleanup."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from pyloto_corp.infra.gcs_exporter import (
    ExportMetadata,
    GCSHistoryExporter,
    create_gcs_exporter,
)

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def mock_gcs_client() -> MagicMock:
    """Mock de cliente GCS."""
    mock = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()

    mock.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    mock_blob.generate_signed_url.return_value = "https://signed-url.example.com"

    return mock


@pytest.fixture
def mock_firestore() -> MagicMock:
    """Mock de cliente Firestore."""
    return MagicMock()


@pytest.fixture
def exporter(mock_gcs_client: MagicMock) -> GCSHistoryExporter:
    """Exporter com mocks."""
    return GCSHistoryExporter(
        bucket_name="test-bucket",
        client=mock_gcs_client,
    )


@pytest.fixture
def exporter_with_firestore(
    mock_gcs_client: MagicMock,
    mock_firestore: MagicMock,
) -> GCSHistoryExporter:
    """Exporter com Firestore para metadados."""
    return GCSHistoryExporter(
        bucket_name="test-bucket",
        client=mock_gcs_client,
        firestore_client=mock_firestore,
    )


@pytest.fixture
def sample_content() -> bytes:
    """Conteúdo de exemplo para export."""
    return b"Historico de conversa\n\nUsuario: Ola\nPyloto: Ola! Como posso ajudar?"


# ============================================================
# Testes: Método save (básico)
# ============================================================


class TestSave:
    """Testes para método save básico."""

    def test_save_returns_gcs_uri(
        self,
        exporter: GCSHistoryExporter,
        sample_content: bytes,
    ) -> None:
        """Save deve retornar URI gs://."""
        result = exporter.save(
            user_key="user_123",
            content=sample_content,
        )

        assert result.startswith("gs://test-bucket/")
        assert "exports/conversations/" in result

    def test_save_uploads_content(
        self,
        exporter: GCSHistoryExporter,
        mock_gcs_client: MagicMock,
        sample_content: bytes,
    ) -> None:
        """Save deve fazer upload do conteúdo."""
        exporter.save(user_key="user_123", content=sample_content)

        mock_blob = mock_gcs_client.bucket.return_value.blob.return_value
        mock_blob.upload_from_string.assert_called_once()

        call_args = mock_blob.upload_from_string.call_args
        assert call_args[0][0] == sample_content
        assert call_args[1]["content_type"] == "text/plain"

    def test_save_with_custom_content_type(
        self,
        exporter: GCSHistoryExporter,
        mock_gcs_client: MagicMock,
    ) -> None:
        """Save deve respeitar content_type customizado."""
        exporter.save(
            user_key="user_123",
            content=b'{"data": "json"}',
            content_type="application/json",
        )

        mock_blob = mock_gcs_client.bucket.return_value.blob.return_value
        call_args = mock_blob.upload_from_string.call_args
        assert call_args[1]["content_type"] == "application/json"

    def test_save_generates_organized_path(
        self,
        exporter: GCSHistoryExporter,
        mock_gcs_client: MagicMock,
        sample_content: bytes,
    ) -> None:
        """Save deve gerar path organizado por data."""
        result = exporter.save(user_key="user_abc", content=sample_content)

        # Deve ter estrutura YYYY/MM/DD
        parts = result.split("/")
        assert "exports" in parts
        assert "conversations" in parts
        # Verificar que tem componentes de data
        assert any(part.isdigit() and len(part) == 4 for part in parts)  # Ano


# ============================================================
# Testes: Método save_with_metadata
# ============================================================


class TestSaveWithMetadata:
    """Testes para save com metadados e URL assinada."""

    def test_save_with_metadata_returns_export_metadata(
        self,
        exporter: GCSHistoryExporter,
        sample_content: bytes,
    ) -> None:
        """Deve retornar ExportMetadata completo."""
        result = exporter.save_with_metadata(
            user_key="user_123",
            content=sample_content,
        )

        assert isinstance(result, ExportMetadata)
        assert result.gcs_uri.startswith("gs://")
        assert result.signed_url is not None
        assert result.user_key == "user_123"
        assert result.size_bytes == len(sample_content)
        assert result.created_at is not None
        assert result.expires_at is not None

    def test_save_with_metadata_generates_signed_url(
        self,
        exporter: GCSHistoryExporter,
        mock_gcs_client: MagicMock,
        sample_content: bytes,
    ) -> None:
        """Deve gerar URL assinada."""
        result = exporter.save_with_metadata(
            user_key="user_123",
            content=sample_content,
        )

        assert result.signed_url == "https://signed-url.example.com"
        mock_blob = mock_gcs_client.bucket.return_value.blob.return_value
        mock_blob.generate_signed_url.assert_called()

    def test_save_with_metadata_custom_expiration(
        self,
        exporter: GCSHistoryExporter,
        mock_gcs_client: MagicMock,
        sample_content: bytes,
    ) -> None:
        """Deve respeitar expiração customizada."""
        result = exporter.save_with_metadata(
            user_key="user_123",
            content=sample_content,
            signed_url_expiration_days=14,
        )

        # Verificar que expires_at é ~14 dias no futuro
        expected_expiration = datetime.now(tz=UTC) + timedelta(days=14)
        assert result.expires_at is not None
        # Diferença deve ser menor que 1 minuto
        diff = abs((result.expires_at - expected_expiration).total_seconds())
        assert diff < 60

    def test_save_with_metadata_persists_to_firestore(
        self,
        exporter_with_firestore: GCSHistoryExporter,
        mock_firestore: MagicMock,
        sample_content: bytes,
    ) -> None:
        """Deve salvar metadados em Firestore."""
        exporter_with_firestore.save_with_metadata(
            user_key="user_123",
            content=sample_content,
        )

        mock_firestore.collection.assert_called_with("exports")
        mock_firestore.collection.return_value.document.return_value.set.assert_called()


# ============================================================
# Testes: Geração de URL assinada
# ============================================================


class TestGenerateSignedUrl:
    """Testes para geração de URL assinada."""

    def test_generate_signed_url_returns_url(
        self,
        exporter: GCSHistoryExporter,
    ) -> None:
        """Deve retornar URL."""
        url = exporter.generate_signed_url("some/object/path.txt")

        assert url == "https://signed-url.example.com"

    def test_generate_signed_url_uses_v4(
        self,
        exporter: GCSHistoryExporter,
        mock_gcs_client: MagicMock,
    ) -> None:
        """Deve usar versão v4 da assinatura."""
        exporter.generate_signed_url("object.txt")

        mock_blob = mock_gcs_client.bucket.return_value.blob.return_value
        call_kwargs = mock_blob.generate_signed_url.call_args[1]
        assert call_kwargs["version"] == "v4"

    def test_generate_signed_url_uses_get_method(
        self,
        exporter: GCSHistoryExporter,
        mock_gcs_client: MagicMock,
    ) -> None:
        """Deve usar método GET."""
        exporter.generate_signed_url("object.txt")

        mock_blob = mock_gcs_client.bucket.return_value.blob.return_value
        call_kwargs = mock_blob.generate_signed_url.call_args[1]
        assert call_kwargs["method"] == "GET"

    def test_generate_signed_url_custom_expiration(
        self,
        exporter: GCSHistoryExporter,
        mock_gcs_client: MagicMock,
    ) -> None:
        """Deve respeitar expiração customizada."""
        exporter.generate_signed_url("object.txt", expiration_days=30)

        mock_blob = mock_gcs_client.bucket.return_value.blob.return_value
        call_kwargs = mock_blob.generate_signed_url.call_args[1]
        assert call_kwargs["expiration"] == timedelta(days=30)


# ============================================================
# Testes: Cleanup de exports antigos
# ============================================================


class TestCleanupOldExports:
    """Testes para cleanup de exports antigos."""

    def test_cleanup_returns_deleted_count(
        self,
        exporter: GCSHistoryExporter,
        mock_gcs_client: MagicMock,
    ) -> None:
        """Deve retornar quantidade de objetos deletados."""
        # Simular lista vazia (nenhum objeto antigo)
        mock_gcs_client.bucket.return_value.list_blobs.return_value = []

        count = exporter.cleanup_old_exports()

        assert count == 0

    def test_cleanup_deletes_old_objects(
        self,
        exporter: GCSHistoryExporter,
        mock_gcs_client: MagicMock,
    ) -> None:
        """Deve deletar objetos mais antigos que retention."""
        # Criar mock de blob antigo
        old_blob = MagicMock()
        old_blob.name = "exports/conversations/2025/01/01/old_export.txt"
        old_blob.time_created = datetime.now(tz=UTC) - timedelta(days=200)

        mock_gcs_client.bucket.return_value.list_blobs.return_value = [old_blob]

        count = exporter.cleanup_old_exports(retention_days=180)

        assert count == 1
        old_blob.delete.assert_called_once()

    def test_cleanup_keeps_recent_objects(
        self,
        exporter: GCSHistoryExporter,
        mock_gcs_client: MagicMock,
    ) -> None:
        """Não deve deletar objetos recentes."""
        recent_blob = MagicMock()
        recent_blob.name = "exports/conversations/2026/01/20/recent.txt"
        recent_blob.time_created = datetime.now(tz=UTC) - timedelta(days=5)

        mock_gcs_client.bucket.return_value.list_blobs.return_value = [recent_blob]

        count = exporter.cleanup_old_exports(retention_days=180)

        assert count == 0
        recent_blob.delete.assert_not_called()

    def test_cleanup_uses_correct_prefix(
        self,
        exporter: GCSHistoryExporter,
        mock_gcs_client: MagicMock,
    ) -> None:
        """Deve usar prefixo correto ao listar blobs."""
        mock_gcs_client.bucket.return_value.list_blobs.return_value = []

        exporter.cleanup_old_exports()

        mock_gcs_client.bucket.return_value.list_blobs.assert_called_with(
            prefix="exports/conversations/"
        )

    def test_cleanup_cleans_firestore_metadata(
        self,
        exporter_with_firestore: GCSHistoryExporter,
        mock_gcs_client: MagicMock,
        mock_firestore: MagicMock,
    ) -> None:
        """Deve limpar metadados do Firestore também."""
        mock_gcs_client.bucket.return_value.list_blobs.return_value = []

        # Simular documentos antigos no Firestore
        mock_doc = MagicMock()
        (
            mock_firestore.collection.return_value.where.return_value.limit.return_value.stream.return_value
        ) = [mock_doc]

        exporter_with_firestore.cleanup_old_exports()

        # Verificar que tentou limpar Firestore
        mock_firestore.collection.assert_called()


# ============================================================
# Testes: Factory
# ============================================================


class TestCreateGcsExporter:
    """Testes para factory function."""

    def test_create_without_firestore(self) -> None:
        """Factory deve funcionar sem Firestore."""
        with patch("pyloto_corp.infra.gcs_exporter.storage.Client"):
            exporter = create_gcs_exporter("test-bucket")
            assert isinstance(exporter, GCSHistoryExporter)

    def test_create_with_firestore(
        self,
        mock_firestore: MagicMock,
    ) -> None:
        """Factory deve aceitar cliente Firestore."""
        with patch("pyloto_corp.infra.gcs_exporter.storage.Client"):
            exporter = create_gcs_exporter(
                "test-bucket",
                firestore_client=mock_firestore,
            )
            assert isinstance(exporter, GCSHistoryExporter)


# ============================================================
# Testes: Edge Cases
# ============================================================


class TestGcsExporterEdgeCases:
    """Testes de casos de borda."""

    def test_empty_content(
        self,
        exporter: GCSHistoryExporter,
    ) -> None:
        """Conteúdo vazio deve funcionar."""
        result = exporter.save(user_key="user_123", content=b"")
        assert result.startswith("gs://")

    def test_large_content(
        self,
        exporter: GCSHistoryExporter,
    ) -> None:
        """Conteúdo grande deve funcionar."""
        large_content = b"x" * 1_000_000  # 1MB
        result = exporter.save(user_key="user_123", content=large_content)
        assert result.startswith("gs://")

    def test_unicode_user_key(
        self,
        exporter: GCSHistoryExporter,
    ) -> None:
        """User key com caracteres especiais deve funcionar."""
        result = exporter.save(
            user_key="user_日本語_123",
            content=b"content",
        )
        assert result.startswith("gs://")

    def test_firestore_error_does_not_fail_save(
        self,
        exporter_with_firestore: GCSHistoryExporter,
        mock_firestore: MagicMock,
        sample_content: bytes,
    ) -> None:
        """Erro de Firestore não deve falhar o save."""
        mock_firestore.collection.return_value.document.return_value.set.side_effect = Exception(
            "Firestore error"
        )

        # Não deve levantar exceção
        result = exporter_with_firestore.save_with_metadata(
            user_key="user_123",
            content=sample_content,
        )

        assert result.gcs_uri is not None

    def test_blob_without_time_created(
        self,
        exporter: GCSHistoryExporter,
        mock_gcs_client: MagicMock,
    ) -> None:
        """Blob sem time_created não deve causar erro."""
        blob = MagicMock()
        blob.name = "exports/old.txt"
        blob.time_created = None

        mock_gcs_client.bucket.return_value.list_blobs.return_value = [blob]

        # Não deve levantar exceção
        count = exporter.cleanup_old_exports()
        assert count == 0
