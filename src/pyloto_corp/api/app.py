"""Fábrica da aplicação FastAPI."""

from __future__ import annotations

from fastapi import FastAPI

from pyloto_corp.ai.orchestrator import AIOrchestrator
from pyloto_corp.api.routes import router
from pyloto_corp.config.settings import Settings, get_settings
from pyloto_corp.infra.dedupe import InMemoryDedupeStore, RedisDedupeStore
from pyloto_corp.observability.logging import configure_logging
from pyloto_corp.observability.middleware import CorrelationIdMiddleware


def create_dedupe_store(settings: Settings):
    """Seleciona o backend de dedupe.

    TODO: aplicar fail-closed em staging/production.
    """

    if settings.dedupe_backend == "redis" and settings.redis_url:
        return RedisDedupeStore(settings.redis_url)

    return InMemoryDedupeStore()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Cria a aplicação FastAPI."""

    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.service_name)

    app = FastAPI(title=settings.service_name, version=settings.version)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(router)

    app.state.settings = settings
    app.state.dedupe_store = create_dedupe_store(settings)
    app.state.orchestrator = AIOrchestrator()

    return app


app = create_app()
