"""Factory para FloodDetector — Detecção distribuída de flood.

Responsabilidades:
- Criar instâncias de FloodDetector baseado em config
- Validar clientes obrigatórios (Redis)
- Injetar thresholds via config

Conforme regras_e_padroes.md (factory pattern, injeção de dependência).
Referência: A4 — Flood/rate-limit em ambiente distribuído (Redis).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pyloto_corp.domain.abuse_detection import (
    FloodDetector,
    InMemoryFloodDetector,
    RedisFloodDetector,
)
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.config.settings import Settings

logger: logging.Logger = get_logger(__name__)


def create_flood_detector(
    backend: str,
    threshold: int = 10,
    time_window_seconds: int = 60,
    redis_client: Any | None = None,
) -> FloodDetector:
    """Factory para FloodDetector.

    Args:
        backend: "redis" ou "memory"
        threshold: Limite de mensagens por janela de tempo (padrão 10)
        time_window_seconds: Janela de tempo em segundos (padrão 60)
        redis_client: Cliente Redis (obrigatório se backend="redis")

    Returns:
        FloodDetector configurado

    Raises:
        ValueError: Se backend inválido ou cliente Redis não fornecido
    """
    if backend == "memory":
        logger.warning(
            "Using in-memory flood detector (dev only, unsuitable for Cloud Run)",
            extra={"threshold": threshold, "window_seconds": time_window_seconds},
        )
        return InMemoryFloodDetector(
            threshold=threshold,
            time_window_seconds=time_window_seconds,
        )

    if backend == "redis":
        if not redis_client:
            msg = "redis_client required for redis backend"
            raise ValueError(msg)

        logger.info(
            "Using Redis flood detector (distributed)",
            extra={"threshold": threshold, "window_seconds": time_window_seconds},
        )
        return RedisFloodDetector(
            redis_client=redis_client,
            threshold=threshold,
            time_window_seconds=time_window_seconds,
        )

    msg = f"Unknown flood detector backend: {backend}"
    raise ValueError(msg)


def create_flood_detector_from_settings(
    settings: Settings, redis_client: Any | None = None
) -> FloodDetector:
    """Cria FloodDetector a partir de Settings.

    Padrão seguro:
    - Desenvolvimento: memory (suficiente para local testing)
    - Produção: redis (obrigatório para Cloud Run multi-instância)

    Args:
        settings: Instância de Settings (carregada de env vars)
        redis_client: Cliente Redis (opcional, será criado se necessário)

    Returns:
        FloodDetector configurado

    Raises:
        ValueError: Se configuração inválida em produção
    """
    backend = settings.flood_detector_backend.lower()
    threshold = settings.flood_threshold
    ttl = settings.flood_ttl_seconds

    # Validação: em produção/staging, memory é inadequado (Cloud Run stateless)
    if (settings.is_production or settings.is_staging) and backend == "memory":
        msg = (
            "FLOOD_DETECTOR_BACKEND=memory is unsuitable for production. "
            "Use 'redis' for Cloud Run distributed instances."
        )
        raise ValueError(msg)

    # Se Redis backend, fornecer cliente
    if backend == "redis" and not redis_client:
        try:
            import redis

            redis_url = settings.redis_url or "redis://localhost:6379"
            redis_client = redis.from_url(redis_url)
            logger.info(
                "Auto-created Redis client for flood detector",
                extra={"url": redis_url},
            )
        except (ImportError, Exception) as e:
            msg = f"Failed to create Redis client for flood detector: {e}"
            raise ValueError(msg) from e

    return create_flood_detector(
        backend=backend,
        threshold=threshold,
        time_window_seconds=ttl,
        redis_client=redis_client,
    )
