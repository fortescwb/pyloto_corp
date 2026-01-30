"""Factory para construção do Pipeline e PipelineConfig.

Responsabilidades:
- Conhecer infra e settings
- Construir um PipelineConfig consistente
- Retornar uma instância de `WhatsAppInboundPipeline`

Não conter lógica de negócio ou chamadas a LLMs.
"""

from __future__ import annotations

from typing import Any

from pyloto_corp.application.pipeline import WhatsAppInboundPipeline
from pyloto_corp.application.pipeline_config import PipelineConfig
from pyloto_corp.config.settings import Settings, get_settings
from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)


def build_whatsapp_pipeline(
    *,
    dedupe_store: Any | None = None,
    session_store: Any | None = None,
    orchestrator: Any | None = None,
    flood_detector: Any | None = None,
    state_selector_client: Any | None = None,
    response_generator_client: Any | None = None,
    master_decider_client: Any | None = None,
    decision_audit_store: Any | None = None,
    settings: Settings | None = None,
) -> WhatsAppInboundPipeline:
    """Constrói e retorna `WhatsAppInboundPipeline` usando infra/settings.

    Parâmetros explícitos têm prioridade; quando ausentes, a função tentará
    resolver via `get_settings()` ou estruturas globais de infra.
    """
    settings = settings or get_settings()

    # Import infra factories apenas aqui
    from pyloto_corp.infra import (
        create_decision_audit_store,
        create_dedupe_store,
        create_session_store,
    )

    # Preencher stores se não fornecidos (ambiente de execução decide backend)
    if dedupe_store is None:
        dedupe_store = create_dedupe_store(settings)
        logger.debug("factory: created dedupe_store via infra create_dedupe_store")

    if session_store is None:
        # Usar backend configurado nas settings (criador interno trata clients quando necessário)
        session_store = create_session_store(settings.session_store_backend)
        logger.debug("factory: created session_store via infra create_session_store")

    if decision_audit_store is None:
        decision_audit_store = create_decision_audit_store(settings)

    # Orchestrator: se não fornecido, criar instância padrão
    if orchestrator is None:
        from pyloto_corp.ai.orchestrator import AIOrchestrator

        orchestrator = AIOrchestrator()

    # Construir SessionManager e incluí‑lo no config para injeção nos pipelines
    from pyloto_corp.application.session.manager import SessionManager

    session_manager = SessionManager(session_store=session_store, logger=logger, settings=settings)

    config = PipelineConfig(
        dedupe_store=dedupe_store,
        session_store=session_store,
        orchestrator=orchestrator,
        flood_detector=flood_detector,
        max_intent_limit=settings.session_max_intents or 3,
        state_selector_client=state_selector_client,
        state_selector_model=settings.state_selector_model,
        state_selector_threshold=settings.state_selector_confidence_threshold,
        state_selector_enabled=settings.state_selector_enabled,
        response_generator_client=response_generator_client,
        response_generator_model=settings.response_generator_model,
        response_generator_enabled=settings.response_generator_enabled,
        response_generator_timeout=settings.response_generator_timeout_seconds,
        response_generator_min_responses=settings.response_generator_min_responses,
        master_decider_client=master_decider_client,
        master_decider_model=settings.master_decider_model,
        master_decider_enabled=settings.master_decider_enabled,
        master_decider_timeout=settings.master_decider_timeout_seconds,
        master_decider_confidence_threshold=settings.master_decider_confidence_threshold,
        decision_audit_store=decision_audit_store,
        session_manager=session_manager,
    )

    return WhatsAppInboundPipeline(config)


# Conveniência: construir pipelines alternativos via factory para garantir padrão
def build_pipeline_v2(
    dedupe_store: Any,
    session_store: Any,
    flood_detector: Any | None = None,
) -> Any:
    """Constrói e retorna um PipelineV2 (compatibilidade)."""
    from pyloto_corp.application.pipeline_v2 import PipelineV2
    from pyloto_corp.application.session.manager import SessionManager

    session_manager = SessionManager(
        session_store=session_store,
        logger=logger,
        settings=get_settings(),
    )

    return PipelineV2(
        dedupe_store=dedupe_store,
        session_store=session_store,
        flood_detector=flood_detector,
        session_manager=session_manager,
    )


def build_pipeline_async(
    dedupe_store: Any,
    async_session_store: Any,
    flood_detector: Any | None = None,
) -> Any:
    """Constrói e retorna um PipelineAsyncV3 (compatibilidade)."""
    from pyloto_corp.application.pipeline_async import PipelineAsyncV3
    from pyloto_corp.application.session.manager import AsyncSessionManager

    async_session_manager = AsyncSessionManager(
        async_session_store=async_session_store,
        logger=logger,
        settings=get_settings(),
    )

    return PipelineAsyncV3(
        dedupe_store=dedupe_store,
        async_session_store=async_session_store,
        flood_detector=flood_detector,
        async_session_manager=async_session_manager,
    )
