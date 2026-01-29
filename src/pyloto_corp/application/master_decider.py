"""Decisor mestre (LLM3) que consolida estado e resposta final."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pyloto_corp.domain.conversation_state import ConversationState
from pyloto_corp.domain.enums import MessageType
from pyloto_corp.domain.master_decision import MasterDecisionInput, MasterDecisionOutput
from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)


def _has_confirmation_text(responses: list[str]) -> tuple[int, str] | None:
    keywords = ["confirme", "confirmar", "finalizar", "encerrar", "resolvemos"]
    for idx, text in enumerate(responses):
        low = text.lower()
        if any(k in low for k in keywords):
            return idx, text
    return None


def _deterministic_rules(data: MasterDecisionInput) -> MasterDecisionOutput | None:
    """Regras baratas para evitar chamada ao LLM."""
    responses = data.response_options.responses
    # Caso não aceito e hint presente -> escolher resposta de confirmação
    if not data.state_decision.accepted and data.state_decision.response_hint:
        found = _has_confirmation_text(responses)
        idx, text = found if found else (0, responses[0])
        reason = "hint_confirmation_auto"
        return MasterDecisionOutput(
            final_state=data.current_state,
            apply_state=False,
            selected_response_index=idx,
            selected_response_text=text,
            message_type=MessageType.TEXT,
            overall_confidence=min(0.7, data.state_decision.confidence or 0.7),
            reason=reason,
            decision_trace={
                "used_hint": True,
                "llm1_confidence": data.state_decision.confidence,
                "llm1_status": data.state_decision.status.value,
                "responses": responses,
            },
        )

    closing_tokens = ["obrigado", "valeu", "ok", "show"]
    if any(tok in data.last_user_message.lower() for tok in closing_tokens):
        idx = 0
        text = responses[idx]
        final_state = (
            data.state_decision.next_state if data.state_decision.accepted else data.current_state
        )
        return MasterDecisionOutput(
            final_state=final_state,
            apply_state=data.state_decision.accepted,
            selected_response_index=idx,
            selected_response_text=text,
            message_type=MessageType.TEXT,
            overall_confidence=min(0.85, data.state_decision.confidence or 0.8),
            reason="closing_detected_auto",
            decision_trace={
                "used_hint": bool(data.state_decision.response_hint),
                "llm1_confidence": data.state_decision.confidence,
                "llm1_status": data.state_decision.status.value,
                "responses": responses,
            },
        )

    return None


def _build_prompt(data: MasterDecisionInput) -> str:
    schema = {
        "type": "object",
        "properties": {
            "final_state": {"type": "string", "enum": [s.value for s in ConversationState]},
            "apply_state": {"type": "boolean"},
            "selected_response_index": {"type": "integer", "minimum": 0},
            "message_type": {"type": "string", "enum": [m.value for m in MessageType]},
            "overall_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string"},
        },
        "required": [
            "final_state",
            "apply_state",
            "selected_response_index",
            "message_type",
            "overall_confidence",
            "reason",
        ],
    }
    parts = [
        "Decida o estado final e qual resposta usar.",
        "Prefira o next_state do LLM1 quando status=accepted.",
        "Use response_hint para reduzir ambiguidade.",
        "Responda apenas JSON válido no schema abaixo.",
        f"current_state={data.current_state.value}",
        f"llm1_next={data.state_decision.next_state.value}",
        f"llm1_status={data.state_decision.status.value}",
        f"llm1_confidence={data.state_decision.confidence}",
        f"Responses: {data.response_options.responses}",
        f"Response tags: {data.response_options.response_style_tags}",
        f"Hint: {data.state_decision.response_hint}",
        f"Safety: {data.response_options.safety_notes}",
        f"Schema: {json.dumps(schema)}",
    ]
    return " ".join(str(p) for p in parts)


def _call_llm(
    llm_client: Any, prompt: str, model: str | None, timeout: float | None
) -> Mapping[str, Any]:
    if hasattr(llm_client, "complete"):
        return llm_client.complete(prompt, model=model, timeout=timeout)
    if hasattr(llm_client, "chat") and hasattr(llm_client.chat, "completions"):
        response = llm_client.chat.completions.create(
            model=model or getattr(llm_client, "_model", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=200,
            timeout=timeout,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
    if callable(llm_client):
        return llm_client(prompt)
    raise RuntimeError("llm_client incompatível")


def _fallback(data: MasterDecisionInput, reason: str) -> MasterDecisionOutput:
    responses = data.response_options.responses
    idx = data.response_options.chosen_index
    idx = idx if idx < len(responses) else 0
    final_state = (
        data.state_decision.next_state if data.state_decision.accepted else data.current_state
    )
    return MasterDecisionOutput(
        final_state=final_state,
        apply_state=data.state_decision.accepted,
        selected_response_index=idx,
        selected_response_text=responses[idx],
        message_type=MessageType.TEXT,
        overall_confidence=min(0.75, data.state_decision.confidence),
        reason=reason,
        decision_trace={
            "llm1_confidence": data.state_decision.confidence,
            "llm1_status": data.state_decision.status.value,
            "responses": responses,
            "fallback": True,
        },
    )


def decide_master(
    data: MasterDecisionInput,
    llm_client: Any,
    *,
    correlation_id: str,
    model: str | None,
    timeout_seconds: float | None,
    confidence_threshold: float = 0.7,
) -> MasterDecisionOutput:
    """Combina LLM1+LLM2 para decisão final executável."""
    deterministic = _deterministic_rules(data)
    if deterministic:
        logger.info(
            "master_decider_deterministic",
            extra={
                "correlation_id": correlation_id,
                "final_state": deterministic.final_state.value,
                "overall_confidence": deterministic.overall_confidence,
                "reason": deterministic.reason,
            },
        )
        deterministic.decision_trace["responses"] = data.response_options.responses
        return deterministic

    try:
        prompt = _build_prompt(data)
        raw = _call_llm(llm_client, prompt, model, timeout_seconds)
        idx = int(raw.get("selected_response_index", data.response_options.chosen_index))
        responses = data.response_options.responses
        idx = idx if 0 <= idx < len(responses) else 0
        final_state_str = raw.get("final_state") or data.state_decision.next_state.value
        apply_state = bool(raw.get("apply_state", True))
        overall_confidence = float(raw.get("overall_confidence", data.state_decision.confidence))
        overall_confidence = max(0.0, min(1.0, overall_confidence))
        reason = raw.get("reason") or "Decisão via LLM"
        message_type_str = raw.get("message_type") or MessageType.TEXT.value
        message_type = MessageType(message_type_str)

        output = MasterDecisionOutput(
            final_state=ConversationState(final_state_str),
            apply_state=apply_state,
            selected_response_index=idx,
            selected_response_text=responses[idx],
            message_type=message_type,
            overall_confidence=overall_confidence,
            reason=reason,
            decision_trace={
                "llm1_confidence": data.state_decision.confidence,
                "llm1_status": data.state_decision.status.value,
                "used_hint": bool(data.state_decision.response_hint),
                "picked_tag": (data.response_options.response_style_tags or [None])[0],
                "responses": responses,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "master_decider_llm_failed",
            extra={
                "correlation_id": correlation_id,
                "error": type(exc).__name__,
                "llm1_status": data.state_decision.status.value,
            },
        )
        output = _fallback(data, "Fallback determinístico por falha do decisor mestre")

    # Regra: se LLM1 não aceitou e estamos forçando apply_state, exigir razão
    if (
        not data.state_decision.accepted
        and output.apply_state
        and output.overall_confidence >= confidence_threshold
        and "confirm" not in output.reason.lower()
    ):
        output.reason = (
            f"{output.reason} (contrariou selector, confiança {output.overall_confidence})"
        )

    logger.info(
        "master_decider_result",
        extra={
            "correlation_id": correlation_id,
            "current_state": data.current_state.value,
            "llm1_next_state": data.state_decision.next_state.value,
            "final_state": output.final_state.value,
            "llm1_status": data.state_decision.status.value,
            "llm1_confidence": data.state_decision.confidence,
            "overall_confidence": output.overall_confidence,
            "selected_response_index": output.selected_response_index,
            "message_type": output.message_type.value,
            "reason": output.reason[:120],
        },
    )
    return output
