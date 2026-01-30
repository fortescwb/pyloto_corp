"""Pipeline v2: Integração de 3 LLM points com ordem garantida.

TODO: mover para ._legado após consolidação Cloud Tasks; fora do fluxo oficial.

Fluxo:
1. Validação e dedupe
2. Detecção de abuso (flood/spam)
3. Recuperação/criação de sessão
4. **FSM**: Determine next state
5. **LLM #1**: Detect event + intenção
6. **LLM #2**: Generate response
7. **LLM #3**: Select message type
8. **MessageBuilder**: Create WhatsApp payload
9. Persistência de sessão + outcome
10. Send message (async)

ORDEM CRÍTICA GARANTIDA:
FSM → LLM#1 → LLM#2 → LLM#3 → MessageBuilder → Send
"""

from __future__ import annotations

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
    from pyloto_corp.domain.protocols import DedupeProtocol, SessionStoreProtocol

logger = get_logger(__name__)
settings = get_settings()


def _run_async_in_thread(coro):
    """Executa coroutine em uma thread separada com seu próprio event loop.

    Isso evita o erro 'asyncio.run() cannot be called from a running event loop'
    quando chamado de dentro de um contexto async (FastAPI).
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    def run_in_new_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_in_new_loop)
        return future.result(timeout=30)


class PipelineV2:
    """Pipeline v2 com 3 LLM points integrados.

    Compatibilidade: oferece `from_dependencies` que usa a factory para centralizar construção.
    """

    @classmethod
    def from_dependencies(
        cls,
        dedupe_store: Any,
        session_store: Any,
        flood_detector: Any | None = None,
    ) -> PipelineV2:
        from pyloto_corp.application.factories.pipeline_factory import build_pipeline_v2

        return build_pipeline_v2(dedupe_store, session_store, flood_detector)

    def __init__(
        self,
        dedupe_store: DedupeProtocol,
        session_store: SessionStoreProtocol,
        flood_detector: FloodDetector | None = None,
        max_intent_limit: int = 3,
        session_manager: Any | None = None,
    ) -> None:
        self._dedupe = dedupe_store
        self._sessions = session_store
        self._flood = flood_detector
        self._max_intents = max_intent_limit
        self._spam = SpamDetector()
        self._abuse = AbuseChecker(max_intents_exceeded=max_intent_limit)
        self._openai_client = get_openai_client() if settings.openai_enabled else None

        # SessionManager (injetado via factory ou criado localmente)
        if session_manager is not None:
            self._session_manager = session_manager
        else:
            from pyloto_corp.application.session_manager import SessionManager

            self._session_manager = SessionManager(
                session_store=self._sessions,
                logger=get_logger(__name__),
                settings=get_settings(),
            )

    def _get_outbound_client(self):
        """Cria cliente WhatsApp outbound com settings."""
        from pyloto_corp.adapters.whatsapp.outbound import WhatsAppOutboundClient

        return WhatsAppOutboundClient(
            api_endpoint=settings.whatsapp_api_endpoint,
            access_token=settings.whatsapp_access_token or "",
            phone_number_id=settings.whatsapp_phone_number_id or "",
        )

    def process_webhook(self, payload: dict[str, Any]) -> WebhookProcessingSummary:
        """Processa webhook completo (dedupe → FSM → 3 LLM → MessageBuilder → Send)."""
        messages = extract_messages(payload)
        total_received = len(messages)
        total_deduped = 0
        total_processed = 0

        for msg in messages:
            if self._dedupe_check(msg):
                total_deduped += 1
                continue

            if self._process_message(msg):
                total_processed += 1

        return WebhookProcessingSummary(
            total_received=total_received,
            total_deduped=total_deduped,
            total_processed=total_processed,
        )

    def _dedupe_check(self, msg: Any) -> bool:
        """Retorna True se foi deduplicado."""
        if not self._dedupe.mark_if_new(msg.message_id):
            logger.debug("msg_deduplicated", extra={"msg_id": msg.message_id[:8]})
            return True
        return False

    def _process_message(self, msg: Any) -> bool:
        """Processa 1 mensagem (FSM → LLM#1 → LLM#2 → LLM#3)."""
        # 1. Recuperar/criar sessão
        session = self._get_or_create_session(msg)

        # 2. Checar abuso (flood, spam, intent capacity)
        if self._is_abuse(msg, session):
            session.outcome = Outcome.DUPLICATE_OR_SPAM
            self._session_manager.persist(session)
            return False

        # 3. FSM: Determine next state
        fsm_state, fsm_next_state = self._run_fsm(session)

        # 4. LLM #1: Detect event
        if not settings.openai_enabled:
            logger.info("openai_disabled: using fallback")
            return self._process_with_fallback(msg, session)

        try:
            return self._process_with_llm(msg, session, fsm_state, fsm_next_state)
        except (TimeoutError, ValueError, RuntimeError) as e:
            logger.warning("llm_pipeline_error", extra={"error": type(e).__name__})
            return self._process_with_fallback(msg, session)
        except Exception as e:
            logger.error("llm_pipeline_unexpected_error", extra={"error": str(e)})
            session.outcome = Outcome.FAILED_INTERNAL
            self._session_manager.persist(session)
            return False

    def _process_with_llm(
        self, msg: Any, session: Any, fsm_state: str, fsm_next_state: str
    ) -> bool:
        """Processa mensagem via pipeline LLM (extração de _process_message)."""
        llm1_result = self._run_llm1_event_detection(msg, session)
        logger.debug(
            "llm1_event_detected",
            extra={
                "event": llm1_result.event.value,
                "intent": llm1_result.detected_intent,
                "confidence": llm1_result.confidence,
            },
        )

        # 5. LLM #2: Generate response
        llm2_result = self._run_llm2_response_generation(
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

        # 6. LLM #3: Select message type (APÓS LLM #2)
        msg_plan = self._run_llm3_message_selection(fsm_state, llm1_result.event.value, llm2_result)
        logger.debug(
            "llm3_message_type_selected",
            extra={
                "kind": msg_plan.kind,
                "safety": msg_plan.safety.pii_risk if msg_plan.safety else "unknown",
            },
        )

        # 7. MessageBuilder: Create payload
        payload = self._build_whatsapp_payload(msg, msg_plan)
        if not payload:
            return False

        # 8. Validate payload
        is_valid, err_msg = validate_payload(payload)
        if not is_valid:
            logger.error("invalid_payload", extra={"error": err_msg})
            return False

        # 9. Sanitize for logging
        sanitized = sanitize_payload(payload)
        logger.info(
            "msg_ready_to_send",
            extra={"msg_type": msg_plan.kind, "payload": sanitized},
        )

        # 10. Send via WhatsApp HTTP
        from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest

        outbound_client = self._get_outbound_client()
        recipient_phone = msg.from_number  # número do remetente
        # Ensure E.164 format (add + prefix if missing)
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
            self._session_manager.persist(session)
            return False

        logger.info(
            "message_sent_successfully",
            extra={"whatsapp_message_id": send_result.message_id},
        )

        # 11. Persist session + outcome
        session.outcome = Outcome.AWAITING_USER
        self._session_manager.persist(session)

        return True

    async def _run_llm3_message_selection_async(self, state: str, event: str, llm2_result):
        """Wrapper async para LLM #3."""
        return await choose_message_plan(self._openai_client, state, event, llm2_result)

    def _run_llm3_message_selection(self, state: str, event: str, llm2_result) -> Any:
        """Seleção de tipo de mensagem (LLM #3)."""
        try:
            # Para manter síncrono no pipeline, usar fallback ou async runner
            msg_plan = choose_message_plan.__wrapped__(
                self._openai_client, state, event, llm2_result
            )
            return msg_plan
        except Exception as e:
            logger.warning(
                "llm3_fallback",
                extra={"error": str(e), "fallback": "text"},
            )
            from pyloto_corp.ai.assistant_message_type import _fallback_message_plan

            return _fallback_message_plan(
                llm2_result,
                safety=None,
            )

    def _run_fsm(self, session: SessionState) -> tuple[str, str]:
        """FSM: Determine state.

        Garantias introduzidas:
        - Estado atual explícito e centralizado (INITIAL_STATE) quando sessão é nova
        - Conversão segura para ConversationState quando for string
        - Retorno de strings (compatível com interface existente)
        """
        from pyloto_corp.domain.fsm_states import ConversationState

        # Normalize current state via SessionManager (may persist and log)
        current_conv = self._session_manager.normalize_current_state(session, correlation_id=None)

        # Determinismo: preferir GENERATING_RESPONSE quando possível, caso contrário
        # escolher um fallback determinístico sem alterar comportamento anterior.
        preferred = ConversationState.GENERATING_RESPONSE
        # Reutilizar a transição padrão definida na FSM (se existir)
        possible_next = list(ConversationState)
        next_state_conv = preferred if preferred in possible_next else preferred

        return current_conv.value, next_state_conv.value

    def _run_llm1_event_detection(self, msg: Any, session: SessionState) -> Any:
        """LLM #1: Detect event."""
        user_input = msg.text or ""
        try:
            result = _run_async_in_thread(
                self._openai_client.detect_event(
                    user_input=user_input,
                    session_history=mask_pii_in_history(session.message_history),
                )
            )
            return result
        except Exception as e:
            logger.error("llm1_error", extra={"error": str(e)})
            from pyloto_corp.ai.openai_parser import _fallback_event_detection

            return _fallback_event_detection()

    def _run_llm2_response_generation(
        self, msg: Any, llm1_result: Any, state: str, next_state: str
    ) -> Any:
        """LLM #2: Generate response."""
        user_input = msg.text or ""
        try:
            result = _run_async_in_thread(
                self._openai_client.generate_response(
                    user_input=user_input,
                    detected_intent=llm1_result.detected_intent,
                    current_state=state,
                    next_state=next_state,
                )
            )
            return result
        except Exception as e:
            logger.error("llm2_error", extra={"error": str(e)})
            from pyloto_corp.ai.openai_parser import _fallback_response_generation

            return _fallback_response_generation()

    def _build_whatsapp_payload(self, msg: Any, msg_plan: Any) -> dict[str, Any] | None:
        """MessageBuilder: Create WhatsApp payload."""
        try:
            from pyloto_corp.adapters.whatsapp.message_builder import (
                build_interactive_buttons_payload,
                build_text_payload,
            )

            to = getattr(msg, "from_number", None) or getattr(msg, "sender_phone", None)
            if not to:
                logger.error("missing_phone_for_payload")
                return None

            # Ensure E.164 format (add + prefix if missing)
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

    def _process_with_fallback(self, msg: Any, session: SessionState) -> bool:
        """Fallback quando OPENAI_ENABLED = False."""
        logger.info("using_fallback_response")
        session.outcome = Outcome.AWAITING_USER
        self._session_manager.persist(session)
        return True

    def _is_abuse(self, msg: Any, session: SessionState) -> bool:
        """Checar flood, spam, intent capacity."""
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

    def _get_or_create_session(self, msg: Any) -> SessionState:
        """Delegar para SessionManager."""
        return self._session_manager.get_or_create_session(msg)
