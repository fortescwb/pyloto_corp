"""Helpers para Upload de Mídia — Validação e Utilitários.

Responsabilidades:
- Validação de conteúdo (tamanho, tipo MIME)
- Cálculo de hash SHA256
- Geração de paths do GCS
- Manutenção de tipos MIME suportados

Conforme regras_e_padroes.md (SRP, funções <50 linhas).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from pyloto_corp.adapters.whatsapp.validators.limits import (
    MAX_FILE_SIZE_MB,
    SUPPORTED_AUDIO_TYPES,
    SUPPORTED_DOCUMENT_TYPES,
    SUPPORTED_IMAGE_TYPES,
    SUPPORTED_VIDEO_TYPES,
)

# Todos os tipos MIME suportados
ALL_SUPPORTED_MIME_TYPES = (
    SUPPORTED_IMAGE_TYPES | SUPPORTED_VIDEO_TYPES | SUPPORTED_AUDIO_TYPES | SUPPORTED_DOCUMENT_TYPES
)


class MediaValidationError(Exception):
    """Erro de validação de mídia (tamanho, tipo, etc.)."""

    pass


def compute_sha256(content: bytes) -> str:
    """Calcula hash SHA256 do conteúdo.

    Args:
        content: Bytes do arquivo

    Returns:
        Hash SHA256 em hexadecimal
    """
    return hashlib.sha256(content).hexdigest()


def validate_content(
    content: bytes,
    mime_type: str,
    max_size_mb: int = MAX_FILE_SIZE_MB,
) -> None:
    """Valida conteúdo antes do upload.

    Args:
        content: Bytes do arquivo
        mime_type: Tipo MIME declarado
        max_size_mb: Tamanho máximo em MB

    Raises:
        MediaValidationError: Se conteúdo inválido
    """
    size_bytes = len(content)
    max_size_bytes = max_size_mb * 1024 * 1024

    if size_bytes == 0:
        raise MediaValidationError("Conteúdo vazio não é permitido")

    if size_bytes > max_size_bytes:
        raise MediaValidationError(f"Arquivo excede limite de {max_size_mb}MB ({size_bytes} bytes)")

    if mime_type not in ALL_SUPPORTED_MIME_TYPES:
        raise MediaValidationError(f"Tipo MIME não suportado: {mime_type}")


def generate_gcs_path(user_key: str, sha256_hash: str, mime_type: str) -> str:
    """Gera path único no GCS baseado em hash e data.

    Args:
        user_key: Chave do usuário
        sha256_hash: Hash SHA256 do conteúdo
        mime_type: Tipo MIME (para extensão)

    Returns:
        Path relativo (sem gs://bucket/)
    """
    now = datetime.now(tz=UTC)
    ext = mime_type.split("/")[-1]
    return f"media/{now.strftime('%Y/%m/%d')}/{user_key}/{sha256_hash[:12]}.{ext}"
