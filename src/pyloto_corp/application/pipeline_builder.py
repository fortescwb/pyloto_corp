"""Construção e configuração do pipeline — factory interna."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyloto_corp.application.pipeline_config import PipelineConfig


def ensure_pipeline_config(config: PipelineConfig | None, **kwargs: Any) -> PipelineConfig:
    """Garante que PipelineConfig existe, convertendo de kwargs se necessário.

    Args:
        config: PipelineConfig, ou None para construir de kwargs
        **kwargs: Parâmetros legados (compatibilidade retroativa)

    Returns:
        PipelineConfig preenchido
    """
    if config is not None:
        return config

    # Construir a partir dos kwargs (compat retroativa)
    from pyloto_corp.application.pipeline_config import PipelineConfig

    return PipelineConfig(
        dedupe_store=kwargs.get("dedupe_store"),
        session_store=kwargs.get("session_store"),
        orchestrator=kwargs.get("orchestrator"),
        flood_detector=kwargs.get("flood_detector"),
        max_intent_limit=kwargs.get("max_intent_limit", 3),
        state_selector_client=kwargs.get("state_selector_client"),
        state_selector_model=kwargs.get("state_selector_model"),
        state_selector_threshold=kwargs.get("state_selector_threshold", 0.7),
        state_selector_enabled=kwargs.get("state_selector_enabled", True),
        response_generator_client=kwargs.get("response_generator_client"),
        response_generator_model=kwargs.get("response_generator_model"),
        response_generator_enabled=kwargs.get("response_generator_enabled", True),
        response_generator_timeout=kwargs.get("response_generator_timeout"),
        response_generator_min_responses=kwargs.get("response_generator_min_responses", 3),
        master_decider_client=kwargs.get("master_decider_client"),
        master_decider_model=kwargs.get("master_decider_model"),
        master_decider_enabled=kwargs.get("master_decider_enabled", True),
        master_decider_timeout=kwargs.get("master_decider_timeout"),
        master_decider_confidence_threshold=kwargs.get("master_decider_confidence_threshold", 0.7),
        decision_audit_store=kwargs.get("decision_audit_store"),
    )
