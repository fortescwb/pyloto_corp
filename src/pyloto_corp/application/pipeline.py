"""Pipeline de processamento inbound — fluxo completo e integrado.

Fluxo:
1. Validação e extração de mensagens do webhook
2. Deduplicação (Redis/Firestore)
3. Detecção de flood/spam/abuso
4. Recuperação ou criação de SessionState
5. Orquestração de IA (intenção + outcome)
6. Enforcement de limites (max 3 intenções)
7. Persistência de sessão
8. Preparação de resposta outbound (se necessário)

Conforme:
- Funcionamento.md § 3.1–3.4 (outcomes canônicos, limites, sessão)
- regras_e_padroes.md (separação de camadas, logs sem PII)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pyloto_corp.adapters.whatsapp.models import WebhookProcessingSummary
from pyloto_corp.adapters.whatsapp.normalizer import extract_messages
from pyloto_corp.application.orchestration_decision import (
    orchestrate_master_decision,
)
from pyloto_corp.application.orchestration_response import (
    orchestrate_response_generation,
)
from pyloto_corp.application.orchestration_state import orchestrate_state_selection
from pyloto_corp.application.pipeline_builder import ensure_pipeline_config
from pyloto_corp.application.response_formatting import apply_otto_intro_if_first
from pyloto_corp.application.session import SessionState
from pyloto_corp.application.session_validation import check_session_validation
from pyloto_corp.domain.abuse_detection import AbuseChecker, FloodDetector, SpamDetector
from pyloto_corp.domain.conversation_state import (
    ConversationState,
    StateSelectorOutput,
)
from pyloto_corp.domain.enums import MessageType, Outcome
from pyloto_corp.domain.master_decision import MasterDecisionOutput
from pyloto_corp.domain.response_generator import (
    ResponseGeneratorOutput,
)
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.ai.orchestrator import AIOrchestrator
    from pyloto_corp.application.pipeline_config import PipelineConfig
    from pyloto_corp.domain.protocols import (
        DecisionAuditStoreProtocol,
        DedupeProtocol,
        SessionStoreProtocol,
    )

logger: logging.Logger = get_logger(__name__)


@dataclass(slots=True)
class ProcessedMessage:
    """Resultado do processamento de uma mensagem (sem PII)."""

    message_id: str
    is_duplicate: bool
    session_id: str
    outcome: Outcome
    reply_text: str | None = None
    state_decision: StateSelectorOutput | None = None
    response_options: ResponseGeneratorOutput | None = None
    master_decision: MasterDecisionOutput | None = None
    final_state: ConversationState | None = None
    selected_response_text: str | None = None
    message_type: MessageType | None = None
    overall_confidence: float | None = None
    decision_reason: str | None = None


@dataclass(slots=True)
class PipelineResult:
    """Resultado do pipeline de processamento."""

    summary: WebhookProcessingSummary
    processed_messages: list[ProcessedMessage]


class WhatsAppInboundPipeline:
    """Pipeline de processamento de webhook inbound.

    Orquestra:
    - Dedupe
    - Gestão de sessão
    - Detecção de abuso (flood, spam)
    - Classificação de IA
    - Persistência
    """

    def __init__(self, config: PipelineConfig | None = None, **kwargs) -> None:
        """Construtor canônico: recebe um `PipelineConfig`.

        Compatibilidade: aceita também a assinatura antiga via keywords (por ex.:
        `dedupe_store=..., session_store=..., orchestrator=...`). Use `from_dependencies`
        quando preferir clareza no código de chamada.
        """
        # Aceita assinatura compatível com a versão antiga (kwargs)
        config = ensure_pipeline_config(config, **kwargs)

        # Dedupe manager (preferred) — created from store if necessary
        from pyloto_corp.application.dedupe.manager import DedupeManager
        from pyloto_corp.config.settings import get_settings

        self._dedupe_store = config.dedupe_store
        self._dedupe_manager = (
            getattr(config, "dedupe_manager", None)
            if getattr(config, "dedupe_manager", None) is not None
            else DedupeManager(store=self._dedupe_store, settings=get_settings())
        )

        self._sessions = config.session_store
        self._orchestrator = config.orchestrator
        self._flood = config.flood_detector
        self._max_intents = config.max_intent_limit
        self._spam = SpamDetector()
        self._abuse_checker = AbuseChecker(max_intents_exceeded=config.max_intent_limit)
        self._state_selector_client = config.state_selector_client
        self._state_selector_model = config.state_selector_model

        # SessionManager (injetado ou criado pela fábrica)
        if getattr(config, "session_manager", None) is not None:
            self._session_manager = config.session_manager
        else:
            from pyloto_corp.application.session_manager import SessionManager
            from pyloto_corp.config.settings import get_settings

            self._session_manager = SessionManager(
                session_store=self._sessions,
                logger=get_logger(__name__),
                settings=get_settings(),
            )
        self._state_selector_threshold = config.state_selector_threshold
        self._state_selector_enabled = config.state_selector_enabled
        self._response_generator_client = config.response_generator_client
        self._response_generator_model = config.response_generator_model
        self._response_generator_enabled = config.response_generator_enabled
        self._response_generator_timeout = config.response_generator_timeout
        self._response_generator_min_responses = config.response_generator_min_responses
        self._master_decider_client = config.master_decider_client
        self._master_decider_model = config.master_decider_model
        self._master_decider_enabled = config.master_decider_enabled
        self._master_decider_timeout = config.master_decider_timeout
        self._master_decider_confidence_threshold = config.master_decider_confidence_threshold
        self._decision_audit_store = config.decision_audit_store

    @classmethod
    def from_dependencies(
        cls,
        dedupe_store: DedupeProtocol,
        session_store: SessionStoreProtocol,
        orchestrator: AIOrchestrator,
        flood_detector: FloodDetector | None = None,
        max_intent_limit: int = 3,
        state_selector_client: Any | None = None,
        state_selector_model: str | None = None,
        state_selector_threshold: float = 0.7,
        state_selector_enabled: bool = True,
        response_generator_client: Any | None = None,
        response_generator_model: str | None = None,
        response_generator_enabled: bool = True,
        response_generator_timeout: float | None = None,
        response_generator_min_responses: int = 3,
        master_decider_client: Any | None = None,
        master_decider_model: str | None = None,
        master_decider_enabled: bool = True,
        master_decider_timeout: float | None = None,
        master_decider_confidence_threshold: float = 0.7,
        decision_audit_store: DecisionAuditStoreProtocol | None = None,
    ) -> WhatsAppInboundPipeline:
        """Compatibilidade retroativa: cria Pipeline a partir da assinatura antiga."""
        from pyloto_corp.application.pipeline_config import PipelineConfig

        config = PipelineConfig(
            dedupe_store=dedupe_store,
            session_store=session_store,
            orchestrator=orchestrator,
            flood_detector=flood_detector,
            max_intent_limit=max_intent_limit,
            state_selector_client=state_selector_client,
            state_selector_model=state_selector_model,
            state_selector_threshold=state_selector_threshold,
            state_selector_enabled=state_selector_enabled,
            response_generator_client=response_generator_client,
            response_generator_model=response_generator_model,
            response_generator_enabled=response_generator_enabled,
            response_generator_timeout=response_generator_timeout,
            response_generator_min_responses=response_generator_min_responses,
            master_decider_client=master_decider_client,
            master_decider_model=master_decider_model,
            master_decider_enabled=master_decider_enabled,
            master_decider_timeout=master_decider_timeout,
            master_decider_confidence_threshold=master_decider_confidence_threshold,
            decision_audit_store=decision_audit_store,
        )
        return cls(config)

    def process_webhook(
        self, payload: dict[str, Any], sender_phone: str | None = None
    ) -> PipelineResult:
        """Processa payload do webhook do WhatsApp."""
        messages = extract_messages(payload)
        total_received = len(messages)
        total_deduped = 0
        processed: list[ProcessedMessage] = []

        for message in messages:
            result, was_dedup = self._process_single_message(message, sender_phone)
            if was_dedup:
                total_deduped += 1
                continue
            if result:
                processed.append(result)

        total_processed = total_received - total_deduped
        return self._build_result(total_received, total_deduped, total_processed, processed)

    def _get_or_create_session(self, message: Any, sender_phone: str | None = None) -> SessionState:
        """Compatibilidade com testes antigos que chamam _get_or_create_session.

        Retorna apenas SessionState (não a tupla (session, is_first)).
        Não adiciona ao histórico (preserva comportamento antigo).
        """
        # Usar get_or_create_session diretamente (sem append ao histórico)
        return self._session_manager.get_or_create_session(message, sender_phone)

    def _process_single_message(
        self, message: Any, sender_phone: str | None
    ) -> tuple[ProcessedMessage | None, bool]:
        """Processa uma mensagem e indica se foi deduplicada."""
        if self._dedupe_manager.inbound(message.message_id):
            logger.debug(
                "Message deduplicated",
                extra={"message_id": message.message_id[:8]},
            )
            return None, True

        session, is_first = self._session_manager.prepare_for_processing(
            message, sender_phone, correlation_id=getattr(message, "message_id", None)
        )

        # Validar sessão (flood, spam, abuso, intent capacity)
        is_valid, rejection_outcome = check_session_validation(
            message, session, self._flood, self._spam, self._abuse_checker
        )
        if not is_valid:
            session.outcome = rejection_outcome
            self._session_manager.persist(session)
            return (
                ProcessedMessage(
                    message_id=message.message_id,
                    is_duplicate=False,
                    session_id=session.session_id,
                    outcome=rejection_outcome,
                ),
                False,
            )

        result = self._orchestrate_and_save(message, session, is_first)
        return result, False

    def _orchestrate_and_save(
        self, message: Any, session: SessionState, is_first: bool = False
    ) -> ProcessedMessage:
        """Orquestra IA, atualiza e persiste sessão."""
        from pyloto_corp.application.session_helpers import (
            is_first_message_of_day,
        )

        # Verificar se é primeira mensagem do dia ANTES de adicionar ao histórico
        msg_ts = getattr(message, "timestamp", None)
        should_prefix = is_first_message_of_day(session, msg_ts)

        # Registrar recebimento (idempotente por message_id) — centralizado no pipeline
        try:
            self._session_manager.append_user_message(
                session, message, correlation_id=getattr(message, "message_id", None)
            )
        except Exception:
            logger.exception("failed_to_append_received_event")

        # Normalizar estado inválido (emite log se necessário)
        self._session_manager.normalize_current_state(
            session, correlation_id=getattr(message, "message_id", None)
        )

        state_decision: StateSelectorOutput | None = None
        response_options: ResponseGeneratorOutput | None = None
        master_decision: MasterDecisionOutput | None = None

        if self._state_selector_enabled:
            state_decision = orchestrate_state_selection(
                session,
                message,
                self._state_selector_client,
                self._state_selector_model,
                self._state_selector_threshold,
            )

        if self._response_generator_enabled and state_decision:
            response_options = orchestrate_response_generation(
                session,
                message,
                state_decision,
                self._response_generator_client,
                self._response_generator_model,
                self._response_generator_timeout,
                self._response_generator_min_responses,
            )

        if self._master_decider_enabled and state_decision and response_options:
            master_decision = orchestrate_master_decision(
                session,
                message,
                state_decision,
                response_options,
                self._master_decider_client,
                self._master_decider_model,
                self._master_decider_timeout,
                self._master_decider_confidence_threshold,
                self._decision_audit_store,
            )

        ai_response = self._orchestrator.process_message(
            message, session=session, is_duplicate=False
        )

        if ai_response.intent:
            session.intent_queue.add_intent(ai_response.intent, confidence=ai_response.confidence)

        session.outcome = ai_response.outcome or Outcome.AWAITING_USER

        # Persistir sessão
        self._session_manager.finalize_after_orchestration(
            session, session.outcome, correlation_id=getattr(message, "message_id", None)
        )

        # Aplicar prefixo do Otto se for a primeira mensagem do dia
        # (should_prefix foi calculado no início do método, antes de adicionar ao histórico)
        ai_response.reply_text = apply_otto_intro_if_first(ai_response.reply_text, should_prefix)

        outcome = session.outcome
        logger.info(
            "Message processed",
            extra={"message_id": message.message_id[:8], "outcome": outcome},
        )
        return ProcessedMessage(
            message_id=message.message_id,
            is_duplicate=False,
            session_id=session.session_id,
            outcome=outcome,
            reply_text=ai_response.reply_text,
            state_decision=state_decision,
            response_options=response_options,
            master_decision=master_decision,
            final_state=master_decision.final_state if master_decision else None,
            selected_response_text=(
                master_decision.selected_response_text if master_decision else None
            ),
            message_type=master_decision.message_type if master_decision else None,
            overall_confidence=master_decision.overall_confidence if master_decision else None,
            decision_reason=master_decision.reason if master_decision else None,
        )

    def _build_result(
        self,
        total_received: int,
        total_deduped: int,
        total_processed: int,
        processed: list[ProcessedMessage],
    ) -> PipelineResult:
        """Monta resultado final do pipeline."""
        logger.info(
            "Webhook complete",
            extra={
                "received": total_received,
                "deduped": total_deduped,
                "processed": total_processed,
            },
        )
        return PipelineResult(
            summary=WebhookProcessingSummary(
                total_received=total_received,
                total_deduped=total_deduped,
                total_processed=total_processed,
            ),
            processed_messages=processed,
        )


def process_whatsapp_webhook(
    payload: dict[str, Any],
    dedupe_store: DedupeProtocol,
    session_store: SessionStoreProtocol,
    orchestrator: AIOrchestrator,
    flood_detector: FloodDetector | None = None,
) -> PipelineResult:
    """Função de conveniência para processamento de webhook."""
    from pyloto_corp.application.factories.pipeline_factory import build_whatsapp_pipeline

    pipeline = build_whatsapp_pipeline(
        dedupe_store=dedupe_store,
        session_store=session_store,
        orchestrator=orchestrator,
        flood_detector=flood_detector,
    )
    return pipeline.process_webhook(payload)
