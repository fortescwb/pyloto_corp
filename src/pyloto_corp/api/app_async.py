"""Fábrica da aplicação FastAPI com suporte a fila assíncrona.

Versão assíncrona que desacopla webhook reception de processamento
usando Cloud Tasks ou fila em memória.
"""

from __future__ import annotations

from fastapi import FastAPI

from pyloto_corp.ai.orchestrator import AIOrchestrator
from pyloto_corp.api.routes_async import router
from pyloto_corp.config.settings import Settings, get_settings
from pyloto_corp.infra.cloud_tasks import CloudTasksDispatcher, LocalCloudTasksClient
from pyloto_corp.infra.decision_audit_store import create_decision_audit_store
from pyloto_corp.infra.dedupe import InMemoryDedupeStore, RedisDedupeStore
from pyloto_corp.infra.flood_detector_factory import create_flood_detector_from_settings
from pyloto_corp.infra.inbound_processing_log import create_inbound_log_store
from pyloto_corp.infra.outbound_dedup_factory import create_outbound_dedupe_store
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


def _create_outbound_store(settings: Settings, redis_client, firestore_client=None):
    """Cria store de idempotência outbound conforme backend."""
    backend = settings.outbound_dedupe_backend.lower()

    if backend == "redis":
        if redis_client is None:
            raise ValueError("outbound_dedupe_backend=redis requer REDIS_URL configurado")
        return create_outbound_dedupe_store("redis", redis_client=redis_client)

    if backend == "firestore":
        if firestore_client is None:
            from google.cloud import firestore

            firestore_client = firestore.Client()
        return create_outbound_dedupe_store("firestore", firestore_client=firestore_client)

    return create_outbound_dedupe_store("memory")


def _build_task_headers(settings: Settings) -> dict[str, str]:
    """Monta headers para chamadas internas protegidas."""
    headers: dict[str, str] = {}
    if settings.internal_task_token:
        headers[settings.internal_token_header] = settings.internal_task_token
    return headers


def _create_tasks_dispatcher(settings: Settings) -> CloudTasksDispatcher:
    """Cria dispatcher de Cloud Tasks (real em staging/prod)."""
    headers = _build_task_headers(settings)
    base_url = (settings.internal_task_base_url or "").rstrip("/")

    use_cloud_tasks = settings.cloud_tasks_enabled or (
        settings.queue_backend.lower() == "cloud_tasks"
    )

    if use_cloud_tasks:
        from google.cloud import tasks_v2

        client = tasks_v2.CloudTasksClient()
        project = settings.gcp_project
    else:
        client = LocalCloudTasksClient()
        project = settings.gcp_project or "local-dev"

    location = settings.gcp_location
    if not project:
        raise ValueError("GCP_PROJECT obrigatório para inicializar Cloud Tasks")

    if not base_url:
        if settings.is_development:
            base_url = "http://localhost"
        else:
            raise ValueError("INTERNAL_TASK_BASE_URL obrigatório para Cloud Tasks")

    return CloudTasksDispatcher(
        client=client,
        project=project,
        location=location,
        base_url=base_url,
        default_headers=headers,
        inbound_queue=settings.inbound_task_queue_name,
        outbound_queue=settings.outbound_task_queue_name,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Cria a aplicação FastAPI com suporte a fila assíncrona."""
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.service_name)

    app = FastAPI(title=settings.service_name, version=settings.version)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(router)

    app.state.settings = settings
    app.state.dedupe_store = create_dedupe_store(settings)

    redis_client = None
    firestore_client = None

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
            raise ValueError("SESSION_STORE_BACKEND=redis mas REDIS_URL não configurado")
        app.state.session_store = create_session_store("redis", client=redis_client)
    elif backend == "firestore":
        from google.cloud import firestore

        firestore_client = firestore.Client()
        app.state.session_store = create_session_store("firestore", client=firestore_client)
    else:
        app.state.session_store = create_session_store("memory")

    app.state.flood_detector = create_flood_detector_from_settings(settings)
    app.state.orchestrator = AIOrchestrator()
    app.state.outbound_dedupe_store = _create_outbound_store(
        settings, redis_client, firestore_client
    )

    # **NOVO**: Criar dispatcher Cloud Tasks
    try:
        tasks_dispatcher = _create_tasks_dispatcher(settings)
        app.state.tasks_dispatcher = tasks_dispatcher
        app.state.message_queue = tasks_dispatcher
        logger.info(
            "tasks_dispatcher_initialized",
            extra={"backend": getattr(settings, "queue_backend", "memory")},
        )
    except Exception as e:
        logger.error(
            "failed_to_initialize_tasks_dispatcher",
            extra={"error": str(e)},
        )
        raise

    # Rastro de processamento inbound
    if redis_client is None and settings.inbound_log_backend.lower() == "redis":
        redis_client = _create_redis_client(settings.redis_url)
        if redis_client is None:
            raise ValueError(
                "INBOUND_LOG_BACKEND=redis mas REDIS_URL não configurado ou conexão falhou"
            )
    if firestore_client is None and settings.inbound_log_backend.lower() == "firestore":
        from google.cloud import firestore

        firestore_client = firestore.Client(
            project=settings.firestore_project_id or settings.gcp_project,
            database=settings.firestore_database_id,
        )

    app.state.inbound_log_store = create_inbound_log_store(
        settings, redis_client=redis_client, firestore_client=firestore_client
    )
    app.state.decision_audit_store = create_decision_audit_store(
        settings, firestore_client=firestore_client
    )

    return app


# Criar instância padrão para uvicorn/Cloud Run
app = create_app()
