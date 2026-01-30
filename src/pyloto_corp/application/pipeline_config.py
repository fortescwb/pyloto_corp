"""PipelineConfig DTO — reduz construtores longos para 1 parâmetro.

Usado para passar dependências do pipeline de forma clara e testável.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pyloto_corp.domain.protocols import (
    DecisionAuditStoreProtocol,
    DedupeProtocol,
    SessionStoreProtocol,
)

if TYPE_CHECKING:
    from pyloto_corp.ai.orchestrator import AIOrchestrator
    from pyloto_corp.domain.abuse_detection import FloodDetector


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    dedupe_store: DedupeProtocol
    session_store: SessionStoreProtocol
    orchestrator: AIOrchestrator
    flood_detector: FloodDetector | None = None
    max_intent_limit: int = 3

    state_selector_client: Any | None = None
    state_selector_model: str | None = None
    state_selector_threshold: float = 0.7
    state_selector_enabled: bool = True

    response_generator_client: Any | None = None
    response_generator_model: str | None = None
    response_generator_enabled: bool = True
    response_generator_timeout: float | None = None
    response_generator_min_responses: int = 3

    master_decider_client: Any | None = None
    master_decider_model: str | None = None
    master_decider_enabled: bool = True
    master_decider_timeout: float | None = None
    master_decider_confidence_threshold: float = 0.7

    decision_audit_store: DecisionAuditStoreProtocol | None = None

    # Optional higher-level managers (injected by factory)
    session_manager: Any | None = None

    # Optional manager injection (preferred over raw store)
    dedupe_manager: Any | None = None
