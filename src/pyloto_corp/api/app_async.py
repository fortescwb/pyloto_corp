"""Fábrica da aplicação FastAPI com suporte a fila assíncrona.

Versão assíncrona que desacopla webhook reception de processamento
usando Cloud Tasks ou fila em memória.
"""

from __future__ import annotations

from fastapi import FastAPI

from pyloto_corp.ai.orchestrator import AIOrchestrator
from pyloto_corp.api.routes_async import router
from pyloto_corp.config.settings import Settings, get_settings
from pyloto_corp.infra.dedupe import InMemoryDedupeStore, RedisDedupeStore
from pyloto_corp.infra.flood_detector_factory import (
    create_flood_detector_from_settings,
)
from pyloto_corp.infra.message_queue import create_message_queue_from_settings
from pyloto_corp.infra.session_store import create_session_store
from pyloto_corp.observability.logging import configure_logging, get_logger
from pyloto_corp.observability.middleware import CorrelationIdMiddleware

logger = get_logger(__name__)


def _create_redis_client(redis_url: str | None):
    """Cria cliente Redis se URL disponível."""
    if not redis_url:
        return None
    try:
        import redis

        return redis.from_url(redis_url, decode_responses=True)
    except ImportError:
        logger.warning("redis package not installed, falling back to memory")
        return None
    except Exception as e:
        logger.warning("redis_connection_failed", extra={"error": str(e)})
        return None


def create_dedupe_store(settings: Settings):
    """Seleciona o backend de dedupe."""
    if settings.dedupe_backend == "redis" and settings.redis_url:
        return RedisDedupeStore(settings.redis_url)

    return InMemoryDedupeStore()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Cria a aplicação FastAPI com suporte a fila assíncrona."""
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.service_name)

    app = FastAPI(title=settings.service_name, version=settings.version)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(router)

    app.state.settings = settings
    app.state.dedupe_store = create_dedupe_store(settings)

    # Validar session store backend
    store_errors = settings.validate_session_store_config()
    if store_errors:
        error_msg = "; ".join(store_errors)
        raise ValueError(
            f"Configuração de session store inválida para '{settings.environment}': {error_msg}"
        )

    # Criar session store
    backend = settings.session_store_backend.lower()
    if backend == "redis":
        redis_client = _create_redis_client(settings.redis_url)
        if redis_client is None:
            raise ValueError(
                "SESSION_STORE_BACKEND=redis mas REDIS_URL não configurado"
            )
        app.state.session_store = create_session_store("redis", client=redis_client)
    elif backend == "firestore":
        from google.cloud import firestore

        firestore_client = firestore.Client()
        app.state.session_store = create_session_store(
            "firestore", client=firestore_client
        )
    else:
        app.state.session_store = create_session_store("memory")

    app.state.flood_detector = create_flood_detector_from_settings(settings)
    app.state.orchestrator = AIOrchestrator()

    # **NOVO**: Criar fila de mensagens (Cloud Tasks ou memória)
    try:
        app.state.message_queue = create_message_queue_from_settings(settings)
        logger.info(
            "message_queue_initialized",
            extra={"backend": getattr(settings, "queue_backend", "memory")},
        )
    except Exception as e:
        logger.error(
            "failed_to_initialize_message_queue",
            extra={"error": str(e)},
        )
        raise

    return app


# Criar instância padrão para uvicorn/Cloud Run
app = create_app()
