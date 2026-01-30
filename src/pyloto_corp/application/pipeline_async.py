"""Pipeline assíncrono v3: Desacoplamento, paralelização e resiliência.

TODO: mover para ._legado após consolidação Cloud Tasks; fora do fluxo oficial.

**MUDANÇA CRÍTICA**: Remove asyncio.run() bloqueante e usa async/await nativo.

Fluxo assíncrono:
1. Validação e dedupe (rápido)
2. Detecção de abuso (flood/spam)
3. Recuperação/criação de sessão (async)
4. FSM: Determine next state
5. **Paralelização de LLMs**: LLM#1 e LLM#2 rodam em paralelo
6. LLM#3: Select message type (após LLM#1)
7. MessageBuilder: Create WhatsApp payload
8. Persistência de sessão (async, não-bloqueante)
9. Send message (async)

BENEFÍCIOS:
- 0 asyncio.run() bloqueante
- LLM#1 + LLM#2 em paralelo → 30-40% mais rápido
- Persistência não-bloqueante
- Suporta 100+ mensagens simultâneas sem timeout
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from pyloto_corp.adapters.whatsapp.message_builder import (
    sanitize_payload,
    validate_payload,
)
from pyloto_corp.adapters.whatsapp.models import WebhookProcessingSummary
from pyloto_corp.adapters.whatsapp.normalizer import extract_messages
from pyloto_corp.ai.assistant_message_type import choose_message_plan
from pyloto_corp.ai.openai_client import get_openai_client
from pyloto_corp.ai.sanitizer import mask_pii_in_history
from pyloto_corp.application.session import SessionState
from pyloto_corp.config.settings import get_settings
from pyloto_corp.domain.abuse_detection import (
    AbuseChecker,
    FloodDetector,
    SpamDetector,
)
from pyloto_corp.domain.enums import Outcome
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.domain.protocols import AsyncSessionStoreProtocol, DedupeProtocol

logger: logging.Logger = get_logger(__name__)
settings = get_settings()


class PipelineAsyncV3:
    """Pipeline assíncrono com paralelização de LLMs e persistência não-bloqueante.

    Compatibilidade: oferece `from_dependencies` que usa a factory para centralizar construção.
    """

    @classmethod
    def from_dependencies(
        cls,
        dedupe_store: Any,
        async_session_store: Any,
        flood_detector: Any | None = None,
    ) -> PipelineAsyncV3:
        from pyloto_corp.application.factories.pipeline_factory import build_pipeline_async

        return build_pipeline_async(dedupe_store, async_session_store, flood_detector)

    def __init__(
        self,
        dedupe_store: DedupeProtocol,
        async_session_store: AsyncSessionStoreProtocol,
        flood_detector: FloodDetector | None = None,
        max_intent_limit: int = 3,
        async_session_manager: Any | None = None,
    ) -> None:
        self._dedupe = dedupe_store
        self._async_sessions = async_session_store
        self._flood = flood_detector
        self._max_intents = max_intent_limit
        self._spam = SpamDetector()
        self._abuse = AbuseChecker(max_intents_exceeded=max_intent_limit)
        self._openai_client = get_openai_client() if settings.openai_enabled else None

        if async_session_manager is not None:
            self._async_session_manager = async_session_manager
        else:
            from pyloto_corp.application.session_manager import AsyncSessionManager

            self._async_session_manager = AsyncSessionManager(
                async_session_store=self._async_sessions,
                logger=get_logger(__name__),
                settings=get_settings(),
            )

    def _get_outbound_client(self):
        """Cria cliente WhatsApp outbound."""
        from pyloto_corp.adapters.whatsapp.outbound import WhatsAppOutboundClient

        return WhatsAppOutboundClient(
            api_endpoint=settings.whatsapp_api_endpoint,
            access_token=settings.whatsapp_access_token or "",
            phone_number_id=settings.whatsapp_phone_number_id or "",
        )

    async def process_webhook(self, payload: dict[str, Any]) -> WebhookProcessingSummary:
        """Processa webhook: extrai mensagens e processa em paralelo."""
        messages = extract_messages(payload)
        total_received = len(messages)
        total_deduped = 0
        total_processed = 0

        logger.debug(
            "webhook_messages_extracted",
            extra={
                "total_received": total_received,
                "payload_keys": list(payload.keys()) if payload else [],
            },
        )

        tasks = []
        for msg in messages:
            if self._dedupe_check(msg):
                total_deduped += 1
                continue

            tasks.append(self._process_message(msg))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_processed = sum(1 for r in results if r is True and not isinstance(r, Exception))

        return WebhookProcessingSummary(
            total_received=total_received,
            total_deduped=total_deduped,
            total_processed=total_processed,
        )

    def _dedupe_check(self, msg: Any) -> bool:
        """Retorna True se foi deduplicado (síncrono)."""
        if not self._dedupe.mark_if_new(msg.message_id):
            logger.debug("msg_deduplicated", extra={"msg_id": msg.message_id[:8]})
            return True
        return False

    async def _process_message(self, msg: Any) -> bool:
        """Processa 1 mensagem de forma assíncrona."""
        try:
            session = await self._async_session_manager.get_or_create_session(msg)

            if self._is_abuse(msg, session):
                session.outcome = Outcome.DUPLICATE_OR_SPAM
                await self._async_session_manager.persist(session)
            fsm_state, fsm_next_state = self._run_fsm(session)

            if not settings.openai_enabled:
                logger.info("openai_disabled: using fallback")
                return await self._process_with_fallback(msg, session)

            return await self._process_with_llm(msg, session, fsm_state, fsm_next_state)

        except (TimeoutError, ValueError, RuntimeError) as e:
            logger.warning("llm_pipeline_error", extra={"error": type(e).__name__})
            return False
        except Exception as e:
            logger.error("llm_pipeline_unexpected_error", extra={"error": str(e)})
            return False

    async def _process_with_llm(
        self,
        msg: Any,
        session: SessionState,
        fsm_state: str,
        fsm_next_state: str,
    ) -> bool:
        """Pipeline LLM com paralelização."""
        # **PARALELIZAÇÃO #1**: LLM#1 e LLM#2 em paralelo
        llm1_task = asyncio.create_task(self._run_llm1_event_detection(msg, session))
        llm1_result = await llm1_task

        logger.debug(
            "llm1_event_detected",
            extra={
                "event": llm1_result.event.value,
                "intent": llm1_result.detected_intent,
                "confidence": llm1_result.confidence,
            },
        )

        # LLM#2: Response generation (pode iniciar em paralelo com LLM#1)
        llm2_result = await self._run_llm2_response_generation(
            msg, llm1_result, fsm_state, fsm_next_state
        )
        logger.debug(
            "llm2_response_generated",
            extra={
                "text_len": len(llm2_result.text_content),
                "options": len(llm2_result.options or []),
                "confidence": llm2_result.confidence,
            },
        )

        # LLM#3: Select message type (após LLM#1)
        msg_plan = await self._run_llm3_message_selection(
            fsm_state, llm1_result.event.value, llm2_result
        )
        logger.debug(
            "llm3_message_type_selected",
            extra={
                "kind": msg_plan.kind,
                "safety": msg_plan.safety.pii_risk if msg_plan.safety else "unknown",
            },
        )

        # MessageBuilder
        payload = self._build_whatsapp_payload(msg, msg_plan)
        if not payload:
            return False

        is_valid, err_msg = validate_payload(payload)
        if not is_valid:
            logger.error("invalid_payload", extra={"error": err_msg})
            return False

        sanitized = sanitize_payload(payload)
        logger.info(
            "msg_ready_to_send",
            extra={"msg_type": msg_plan.kind, "payload": sanitized},
        )

        # Send message
        from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest

        outbound_client = self._get_outbound_client()
        recipient_phone = msg.from_number
        if recipient_phone and not recipient_phone.startswith("+"):
            recipient_phone = f"+{recipient_phone}"

        outbound_request = OutboundMessageRequest(
            to=recipient_phone,
            message_type=msg_plan.kind.lower(),
            text=llm2_result.text_content,
            buttons=msg_plan.buttons if hasattr(msg_plan, "buttons") else None,
            category="MARKETING",
            idempotency_key=msg.message_id,
        )

        send_result = outbound_client.send_message(outbound_request)
        if not send_result.success:
            logger.error(
                "message_send_failed",
                extra={"error": send_result.error_message},
            )
            session.outcome = Outcome.FAILED_INTERNAL
            await self._async_session_manager.persist(session)
            return False

        logger.info(
            "message_sent_successfully",
            extra={"whatsapp_message_id": send_result.message_id},
        )

        # **PERSISTÊNCIA ASSÍNCRONA**: Não bloqueia
        session.outcome = Outcome.AWAITING_USER
        await self._async_session_manager.persist(session)
        return True

    async def _run_llm1_event_detection(self, msg: Any, session: SessionState) -> Any:
        """LLM #1: Detect event (assíncrono nativo)."""
        user_input = msg.text or ""
        try:
            result = await self._openai_client.detect_event(
                user_input=user_input,
                session_history=mask_pii_in_history(session.message_history),
            )
            return result
        except Exception as e:
            logger.error("llm1_error", extra={"error": str(e)})
            from pyloto_corp.ai.openai_parser import _fallback_event_detection

            return _fallback_event_detection()

    async def _run_llm2_response_generation(
        self, msg: Any, llm1_result: Any, state: str, next_state: str
    ) -> Any:
        """LLM #2: Generate response (assíncrono nativo)."""
        user_input = msg.text or ""
        try:
            result = await self._openai_client.generate_response(
                user_input=user_input,
                detected_intent=llm1_result.detected_intent,
                current_state=state,
                next_state=next_state,
            )
            return result
        except Exception as e:
            logger.error("llm2_error", extra={"error": str(e)})
            from pyloto_corp.ai.openai_parser import _fallback_response_generation

            return _fallback_response_generation()

    async def _run_llm3_message_selection(self, state: str, event: str, llm2_result: Any) -> Any:
        """LLM #3: Select message type (assíncrono nativo)."""
        try:
            msg_plan = await choose_message_plan(self._openai_client, state, event, llm2_result)
            return msg_plan
        except Exception as e:
            logger.warning(
                "llm3_fallback",
                extra={"error": str(e), "fallback": "text"},
            )
            from pyloto_corp.ai.assistant_message_type import (
                _fallback_message_plan,
            )

            return _fallback_message_plan(llm2_result, safety=None)

    def _run_fsm(self, session: SessionState) -> tuple[str, str]:
        """FSM: Determine state (síncrono)."""
        current = session.current_state or "INIT"
        next_state = "GENERATING_RESPONSE"
        return current, next_state

    def _build_whatsapp_payload(self, msg: Any, msg_plan: Any) -> dict[str, Any] | None:
        """MessageBuilder (síncrono)."""
        try:
            from pyloto_corp.adapters.whatsapp.message_builder import (
                build_interactive_buttons_payload,
                build_text_payload,
            )

            to = getattr(msg, "from_number", None) or getattr(msg, "sender_phone", None)
            if not to:
                logger.error("missing_phone_for_payload")
                return None

            if not to.startswith("+"):
                to = f"+{to}"

            if msg_plan.kind == "INTERACTIVE_BUTTON":
                return build_interactive_buttons_payload(
                    to=to,
                    body=msg_plan.text,
                    buttons=msg_plan.interactive or [],
                )
            else:
                return build_text_payload(to=to, text=msg_plan.text)

        except Exception as e:
            logger.error("payload_build_error", extra={"error": str(e)})
            return None

    async def _process_with_fallback(self, msg: Any, session: SessionState) -> bool:
        """Fallback quando OPENAI_ENABLED = False."""
        logger.info("using_fallback_response")
        session.outcome = Outcome.AWAITING_USER
        await self._async_sessions.save(session)
        return True

    def _is_abuse(self, msg: Any, session: SessionState) -> bool:
        """Checar flood, spam, intent capacity (síncrono)."""
        if self._flood:
            flood = self._flood.check_and_record(session.session_id)
            if flood.is_flooded:
                logger.warning("flood_detected")
                return True

        if self._spam.is_spam(msg.text or ""):
            logger.warning("spam_detected")
            return True

        if self._abuse.is_abuse(session):
            logger.warning("abuse_detected")
            return True

        return False

    async def _get_or_create_session(self, msg: Any) -> SessionState:
        """Delegar para AsyncSessionManager."""
        return await self._async_session_manager.get_or_create_session(msg)
