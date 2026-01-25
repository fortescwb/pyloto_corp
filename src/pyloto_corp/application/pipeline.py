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
from pyloto_corp.application.session import SessionState
from pyloto_corp.domain.abuse_detection import (
    AbuseChecker,
    FloodDetector,
    SpamDetector,
)
from pyloto_corp.domain.enums import Outcome
from pyloto_corp.observability.logging import get_logger
from pyloto_corp.utils.ids import new_session_id

if TYPE_CHECKING:
    from pyloto_corp.ai.orchestrator import AIOrchestrator
    from pyloto_corp.infra.dedupe import DedupeStore
    from pyloto_corp.infra.session_store import SessionStore

logger: logging.Logger = get_logger(__name__)


@dataclass(slots=True)
class ProcessedMessage:
    """Resultado do processamento de uma mensagem (sem PII)."""

    message_id: str
    is_duplicate: bool
    session_id: str
    outcome: Outcome
    reply_text: str | None = None


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

    def __init__(
        self,
        dedupe_store: DedupeStore,
        session_store: SessionStore,
        orchestrator: AIOrchestrator,
        flood_detector: FloodDetector | None = None,
        max_intent_limit: int = 3,
    ) -> None:
        self._dedupe = dedupe_store
        self._sessions = session_store
        self._orchestrator = orchestrator
        self._flood = flood_detector
        self._max_intents = max_intent_limit
        self._spam = SpamDetector()
        self._abuse_checker = AbuseChecker(max_intents_exceeded=max_intent_limit)

    def process_webhook(
        self, payload: dict[str, Any], sender_phone: str | None = None
    ) -> PipelineResult:
        """Processa payload do webhook do WhatsApp.

        Args:
            payload: Payload bruto do webhook Meta
            sender_phone: Telefone do remetente (se disponível)

        Returns:
            PipelineResult com resumo e detalhes de processamento
        """

        messages = extract_messages(payload)
        total_received = len(messages)
        total_deduped = 0
        total_processed = 0
        processed: list[ProcessedMessage] = []

        for message in messages:
            # Etapa 1: Deduplicação
            is_duplicate = self._dedupe.check_and_mark(message.message_id)
            if is_duplicate:
                total_deduped += 1
                logger.debug(
                    "Message deduplicated",
                    extra={"message_id": message.message_id[:8] + "..."},
                )
                continue

            total_processed += 1

            # Etapa 2: Recuperar/criar sessão
            session = self._get_or_create_session(message, sender_phone)

            # Etapa 3: Verificar flood
            if self._flood:
                flood_result = self._flood.check_and_record(session.session_id)
                if flood_result.is_flooded:
                    logger.warning(
                        "Message rejected: flood detected",
                        extra={
                            "session_id": session.session_id[:8] + "...",
                            "message_count": flood_result.message_count,
                        },
                    )
                    session.outcome = Outcome.DUPLICATE_OR_SPAM
                    self._sessions.save(session)
                    processed.append(
                        ProcessedMessage(
                            message_id=message.message_id,
                            is_duplicate=False,
                            session_id=session.session_id,
                            outcome=Outcome.DUPLICATE_OR_SPAM,
                        )
                    )
                    continue

            # Etapa 4: Verificar spam
            if self._spam.is_spam(message.text or ""):
                logger.warning(
                    "Message rejected: spam detected",
                    extra={"session_id": session.session_id[:8] + "..."},
                )
                session.outcome = Outcome.DUPLICATE_OR_SPAM
                self._sessions.save(session)
                processed.append(
                    ProcessedMessage(
                        message_id=message.message_id,
                        is_duplicate=False,
                        session_id=session.session_id,
                        outcome=Outcome.DUPLICATE_OR_SPAM,
                    )
                )
                continue

            # Etapa 5: Verificar abuso
            if self._abuse_checker.is_abuse(session):
                logger.warning(
                    "Message rejected: abuse pattern detected",
                    extra={"session_id": session.session_id[:8] + "..."},
                )
                session.outcome = Outcome.DUPLICATE_OR_SPAM
                self._sessions.save(session)
                processed.append(
                    ProcessedMessage(
                        message_id=message.message_id,
                        is_duplicate=False,
                        session_id=session.session_id,
                        outcome=Outcome.DUPLICATE_OR_SPAM,
                    )
                )
                continue

            # Etapa 6: Verificar se limite de intenções foi atingido
            if session.intent_queue.is_at_capacity():
                logger.info(
                    "Session at max intents capacity",
                    extra={
                        "session_id": session.session_id[:8] + "...",
                        "total_intents": session.intent_queue.total_intents(),
                    },
                )
                session.outcome = Outcome.SCHEDULED_FOLLOWUP
                self._sessions.save(session)
                processed.append(
                    ProcessedMessage(
                        message_id=message.message_id,
                        is_duplicate=False,
                        session_id=session.session_id,
                        outcome=Outcome.SCHEDULED_FOLLOWUP,
                    )
                )
                continue

            # Etapa 7: Orquestrar decisão de outcome
            ai_response = self._orchestrator.process_message(
                message, session=session, is_duplicate=False
            )

            # Etapa 8: Atualizar sessão com resultado
            if ai_response.intent:
                session.intent_queue.add_intent(
                    ai_response.intent, confidence=ai_response.confidence
                )

            if ai_response.outcome:
                session.outcome = ai_response.outcome

            # Etapa 9: Persistir sessão
            try:
                self._sessions.save(session)
            except Exception as e:
                logger.error(
                    "Failed to save session",
                    extra={
                        "session_id": session.session_id[:8] + "...",
                        "error": str(e),
                    },
                )

            processed.append(
                ProcessedMessage(
                    message_id=message.message_id,
                    is_duplicate=False,
                    session_id=session.session_id,
                    outcome=ai_response.outcome or Outcome.AWAITING_USER,
                    reply_text=ai_response.reply_text,
                )
            )

            logger.info(
                "Message processed",
                extra={
                    "message_id": message.message_id[:8] + "...",
                    "session_id": session.session_id[:8] + "...",
                    "outcome": ai_response.outcome,
                },
            )

        summary = WebhookProcessingSummary(
            total_received=total_received,
            total_deduped=total_deduped,
            total_processed=total_processed,
        )

        logger.info(
            "Webhook processing complete",
            extra={
                "total_received": total_received,
                "total_deduped": total_deduped,
                "total_processed": total_processed,
            },
        )

        return PipelineResult(summary=summary, processed_messages=processed)

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
    dedupe_store: DedupeStore,
    session_store: SessionStore,
    orchestrator: AIOrchestrator,
) -> PipelineResult:
    """Função de conveniência para processamento de webhook.

    Args:
        payload: Payload bruto do webhook Meta
        dedupe_store: Store de deduplicação
        session_store: Store de persistência de sessão
        orchestrator: Orquestrador de IA

    Returns:
        PipelineResult com resumo e detalhes
    """

    pipeline = WhatsAppInboundPipeline(
        dedupe_store=dedupe_store,
        session_store=session_store,
        orchestrator=orchestrator,
    )

    return pipeline.process_webhook(payload)
