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
from pyloto_corp.application.master_decider import decide_master
from pyloto_corp.application.response_generator import generate_response_options
from pyloto_corp.application.session import SessionState
from pyloto_corp.application.state_selector import select_next_state
from pyloto_corp.domain.abuse_detection import AbuseChecker, FloodDetector, SpamDetector
from pyloto_corp.domain.conversation_state import (
    ConversationState,
    StateSelectorInput,
    StateSelectorOutput,
)
from pyloto_corp.domain.enums import MessageType, Outcome
from pyloto_corp.domain.master_decision import MasterDecisionOutput
from pyloto_corp.domain.response_generator import (
    ResponseGeneratorInput,
    ResponseGeneratorOutput,
)
from pyloto_corp.observability.logging import get_logger
from pyloto_corp.utils.ids import new_session_id

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

    def __init__(self, config: PipelineConfig) -> None:
        """Construtor canônico: recebe apenas um PipelineConfig.

        Use `from_dependencies` se for necessário compatibilidade com a assinatura antiga.
        """
        self._dedupe = config.dedupe_store
        self._sessions = config.session_store
        self._orchestrator = config.orchestrator
        self._flood = config.flood_detector
        self._max_intents = config.max_intent_limit
        self._spam = SpamDetector()
        self._abuse_checker = AbuseChecker(max_intents_exceeded=config.max_intent_limit)
        self._state_selector_client = config.state_selector_client
        self._state_selector_model = config.state_selector_model
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

    def _process_single_message(
        self, message: Any, sender_phone: str | None
    ) -> tuple[ProcessedMessage | None, bool]:
        """Processa uma mensagem e indica se foi deduplicada."""
        if not self._dedupe.mark_if_new(message.message_id):
            logger.debug(
                "Message deduplicated",
                extra={"message_id": message.message_id[:8]},
            )
            return None, True

        session = self._get_or_create_session(message, sender_phone)

        abuse_result = self._check_abuse(message, session)
        if abuse_result:
            return abuse_result, False

        capacity_result = self._check_intent_capacity(message, session)
        if capacity_result:
            return capacity_result, False

        result = self._orchestrate_and_save(message, session)
        return result, False

    def _check_abuse(self, message: Any, session: SessionState) -> ProcessedMessage | None:
        """Verifica flood, spam e padrões de abuso. Retorna ProcessedMessage se rejeitado."""
        # Verificar flood
        if self._flood:
            flood_result = self._flood.check_and_record(session.session_id)
            if flood_result.is_flooded:
                logger.warning(
                    "Message rejected: flood",
                    extra={"session_id": session.session_id[:8]},
                )
                return self._reject_message(message, session, Outcome.DUPLICATE_OR_SPAM)

        # Verificar spam
        if self._spam.is_spam(message.text or ""):
            logger.warning(
                "Message rejected: spam",
                extra={"session_id": session.session_id[:8]},
            )
            return self._reject_message(message, session, Outcome.DUPLICATE_OR_SPAM)

        # Verificar abuso
        if self._abuse_checker.is_abuse(session):
            logger.warning(
                "Message rejected: abuse",
                extra={"session_id": session.session_id[:8]},
            )
            return self._reject_message(message, session, Outcome.DUPLICATE_OR_SPAM)

        return None

    def _check_intent_capacity(
        self, message: Any, session: SessionState
    ) -> ProcessedMessage | None:
        """Verifica se sessão atingiu limite de intenções."""
        if session.intent_queue.is_at_capacity():
            logger.info(
                "Session at max intents",
                extra={"session_id": session.session_id[:8]},
            )
            return self._reject_message(message, session, Outcome.SCHEDULED_FOLLOWUP)
        return None

    def _reject_message(
        self, message: Any, session: SessionState, outcome: Outcome
    ) -> ProcessedMessage:
        """Rejeita mensagem com outcome específico e persiste sessão."""
        session.outcome = outcome
        self._sessions.save(session)
        return ProcessedMessage(
            message_id=message.message_id, is_duplicate=False,
            session_id=session.session_id, outcome=outcome,
        )

    def _orchestrate_and_save(
        self, message: Any, session: SessionState
    ) -> ProcessedMessage:
        """Orquestra IA, atualiza e persiste sessão."""
        state_decision: StateSelectorOutput | None = None
        response_options: ResponseGeneratorOutput | None = None

        if self._state_selector_enabled:
            selector_input = StateSelectorInput(
                current_state=ConversationState(session.current_state),
                possible_next_states=[
                    ConversationState.AWAITING_USER,
                    ConversationState.HANDOFF_HUMAN,
                    ConversationState.SELF_SERVE_INFO,
                    ConversationState.ROUTE_EXTERNAL,
                    ConversationState.SCHEDULED_FOLLOWUP,
                ],
                message_text=message.text or "",
                history_summary=[h.get("summary", "") for h in session.message_history],
            )
            state_decision = select_next_state(
                selector_input,
                self._state_selector_client,
                correlation_id=message.message_id,
                model=self._state_selector_model,
                confidence_threshold=self._state_selector_threshold,
            )
            if state_decision.accepted:
                session.current_state = state_decision.next_state.value
            else:
                session.message_history.append(
                    {"summary": "state_hint", "hint": state_decision.response_hint}
                )

        if self._response_generator_enabled and state_decision:
            rg_input = ResponseGeneratorInput(
                last_user_message=message.text or "",
                day_history=session.message_history,
                state_decision=state_decision,
                current_state=ConversationState(session.current_state),
                candidate_next_state=state_decision.selected_state,
                confidence=state_decision.confidence,
                response_hint=state_decision.response_hint,
            )
            response_options = generate_response_options(
                rg_input,
                self._response_generator_client,
                correlation_id=message.message_id,
                model=self._response_generator_model,
                timeout_seconds=self._response_generator_timeout,
                min_responses=self._response_generator_min_responses,
            )

        master_decision: MasterDecisionOutput | None = None
        if self._master_decider_enabled and state_decision and response_options:
            from pyloto_corp.domain.master_decision import MasterDecisionInput

            md_input = MasterDecisionInput(
                last_user_message=message.text or "",
                day_history=session.message_history,
                state_decision=state_decision,
                response_options=response_options,
                current_state=ConversationState(session.current_state),
                correlation_id=message.message_id,
            )
            master_decision = decide_master(
                md_input,
                self._master_decider_client,
                correlation_id=message.message_id,
                model=self._master_decider_model,
                timeout_seconds=self._master_decider_timeout,
                confidence_threshold=self._master_decider_confidence_threshold,
            )
            if master_decision.apply_state:
                session.current_state = master_decision.final_state.value
            if self._decision_audit_store:
                try:
                    self._decision_audit_store.append(
                        {
                            "timestamp": getattr(message, "timestamp", None),
                            "correlation_id": message.message_id,
                            "final_state": master_decision.final_state.value,
                            "apply_state": master_decision.apply_state,
                            "selected_response_index": master_decision.selected_response_index,
                            "message_type": master_decision.message_type.value,
                            "overall_confidence": master_decision.overall_confidence,
                            "reason": master_decision.reason,
                            "llm1": {
                                "status": state_decision.status.value,
                                "confidence": state_decision.confidence,
                                "next_state": state_decision.next_state.value,
                            },
                            "responses_fingerprint": hash(tuple(response_options.responses)),
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "decision_audit_append_failed",
                        extra={"error": str(exc), "correlation_id": message.message_id},
                    )

        ai_response = self._orchestrator.process_message(
            message, session=session, is_duplicate=False
        )

        if ai_response.intent:
            session.intent_queue.add_intent(
                ai_response.intent, confidence=ai_response.confidence
            )

        session.outcome = ai_response.outcome or Outcome.AWAITING_USER

        try:
            self._sessions.save(session)
        except Exception as e:
            logger.error(
                "Failed to save session",
                extra={"session_id": session.session_id[:8], "error": str(e)},
            )

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

    def _get_or_create_session(
        self, message: Any, sender_phone: str | None = None
    ) -> SessionState:
        """Recupera sessão existente ou cria nova.

        Usa message.chat_id como chave se disponível.
        """

        # Tentar extrair chat_id da mensagem normalizada
        chat_id = getattr(message, "chat_id", None)

        if chat_id:
            session = self._sessions.load(chat_id)
            if session:
                logger.debug(
                    "Session loaded",
                    extra={"session_id": chat_id[:8] + "..."},
                )
                return session

        # Criar nova sessão
        session_id = new_session_id()
        session = SessionState(session_id=session_id)

        logger.info(
            "New session created",
            extra={
                "session_id": session_id[:8] + "...",
                "chat_id": chat_id[:8] + "..." if chat_id else None,
            },
        )

        return session


def process_whatsapp_webhook(
    payload: dict[str, Any],
    dedupe_store: DedupeProtocol,
    session_store: SessionStoreProtocol,
    orchestrator: AIOrchestrator,
    flood_detector: FloodDetector | None = None,
) -> PipelineResult:
    """Função de conveniência para processamento de webhook.

    Args:
        payload: Payload bruto do webhook Meta
        dedupe_store: Store de deduplicação
        session_store: Store de persistência de sessão
        orchestrator: Orquestrador de IA
        flood_detector: Detector de flood (opcional)

    Returns:
        PipelineResult com resumo e detalhes
    """
    pipeline = WhatsAppInboundPipeline.from_dependencies(
        dedupe_store=dedupe_store,
        session_store=session_store,
        orchestrator=orchestrator,
        flood_detector=flood_detector,
    )

    return pipeline.process_webhook(payload)
