"""Orquestração de decisão final (Master Decider LLM).

Responsabilidade única: chamar master decider LLM e retornar decisão final.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pyloto_corp.application.master_decider import decide_master
from pyloto_corp.domain.conversation_state import ConversationState
from pyloto_corp.domain.master_decision import MasterDecisionInput
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.domain.conversation_state import StateSelectorOutput
    from pyloto_corp.domain.master_decision import MasterDecisionOutput
    from pyloto_corp.domain.response_generator import ResponseGeneratorOutput

logger = get_logger(__name__)


def orchestrate_master_decision(
    session: Any,
    message: Any,
    state_decision: StateSelectorOutput,
    response_options: ResponseGeneratorOutput,
    master_decider_client: Any,
    master_decider_model: str | None,
    master_decider_timeout: int,
    master_decider_confidence_threshold: float,
    decision_audit_store: Any | None = None,
) -> MasterDecisionOutput | None:
    """Orquestra decisão final via master decider LLM.

    Retorna MasterDecisionOutput ou None se desabilitado.
    """
    # Normalizar estado inválido para fallback seguro
    try:
        current_conv = ConversationState(session.current_state)
    except Exception:
        current_conv = ConversationState.AWAITING_USER

    md_input = MasterDecisionInput(
        last_user_message=message.text or "",
        day_history=session.message_history,
        state_decision=state_decision,
        response_options=response_options,
        current_state=current_conv,
        correlation_id=message.message_id,
    )

    master_decision = decide_master(
        md_input,
        master_decider_client,
        correlation_id=message.message_id,
        model=master_decider_model,
        timeout_seconds=master_decider_timeout,
        confidence_threshold=master_decider_confidence_threshold,
    )

    if master_decision.apply_state:
        session.current_state = master_decision.final_state.value

    if decision_audit_store:
        try:
            decision_audit_store.append(
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
        except Exception as exc:
            logger.error(
                "decision_audit_append_failed",
                extra={"error": str(exc), "correlation_id": message.message_id},
            )

    return master_decision
