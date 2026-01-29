"""Seletor de estado (LLM #1) com confidence gate e precheck determinístico."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pyloto_corp.domain.conversation_state import (
    ConversationState,
    StateSelectorInput,
    StateSelectorOutput,
    StateSelectorStatus,
)
from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)


def _deterministic_precheck(
    data: StateSelectorInput, threshold: float
) -> tuple[float, str | None, StateSelectorStatus]:
    """Pré-checagem barata para encerramento ou nova solicitação."""
    text = (data.message_text or "").lower()
    closing_tokens = ["ok", "entendi", "obrigado", "valeu", "show"]
    new_req_tokens = ["agora", "outra coisa", "além disso", "também", "mais uma"]

    hint = None
    status = StateSelectorStatus.IN_PROGRESS
    max_confidence = 1.0

    if any(tok in text for tok in new_req_tokens):
        status = StateSelectorStatus.NEW_REQUEST_DETECTED
        hint = "Parece um novo pedido. Confirme se é uma nova demanda antes de avançar."
        max_confidence = min(max_confidence, threshold - 0.01)

    if any(tok == text.strip() for tok in closing_tokens) or (
        any(tok in text for tok in closing_tokens) and data.open_items
    ):
        status = StateSelectorStatus.NEEDS_CLARIFICATION
        hint = "Confirme se o atendimento foi concluído ou se há pendências em aberto."
        max_confidence = min(max_confidence, threshold - 0.01)

    return max_confidence, hint, status


def _build_prompt(data: StateSelectorInput) -> str:
    """Monta prompt com schema JSON estrito."""
    schema = {
        "type": "object",
        "properties": {
            "selected_state": {
                "type": "string",
                "enum": [s.value for s in data.possible_next_states + [data.current_state]],
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "status": {
                "type": "string",
                "enum": [s.value for s in StateSelectorStatus],
            },
            "open_items": {"type": "array", "items": {"type": "string"}},
            "fulfilled_items": {"type": "array", "items": {"type": "string"}},
            "detected_requests": {"type": "array", "items": {"type": "string"}},
            "response_hint": {"type": "string"},
        },
        "required": ["selected_state", "confidence", "status"],
    }
    return (
        "Você é um seletor de estado. Responda somente JSON válido.\n"
        f"Estado atual: {data.current_state.value}\n"
        f"Próximos possíveis: {[s.value for s in data.possible_next_states]}\n"
        f"Mensagem: {data.message_text}\n"
        f"Resumo histórico: {data.history_summary}\n"
        f"Pendências: {data.open_items}\n"
        f"Atendidas: {data.fulfilled_items}\n"
        f"Requests detectados: {data.detected_requests}\n"
        f"Schema: {json.dumps(schema)}"
    )


def _call_llm(llm_client: Any, prompt: str, model: str | None = None) -> Mapping[str, Any]:
    """Chama LLM de forma resiliente, esperando JSON."""
    if llm_client is None:
        msg = "llm_client ausente"
        raise RuntimeError(msg)

    # Interface simples: objeto com método complete(prompt, model=None)
    if hasattr(llm_client, "complete"):
        return llm_client.complete(prompt, model=model)

    # Compatibilidade com OpenAIClientManager: utilizar chat.completions.create
    if hasattr(llm_client, "chat") and hasattr(llm_client.chat, "completions"):
        response = llm_client.chat.completions.create(
            model=model or getattr(llm_client, "_model", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=200,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    # Último recurso: tentar callable
    if callable(llm_client):
        return llm_client(prompt)

    msg = "llm_client não compatível"
    raise RuntimeError(msg)


def select_next_state(
    data: StateSelectorInput,
    llm_client: Any,
    *,
    correlation_id: str,
    model: str | None = None,
    confidence_threshold: float = 0.7,
) -> StateSelectorOutput:
    """Executa seleção de estado com gate de confiança e fallback seguro."""
    max_confidence, pre_hint, pre_status = _deterministic_precheck(
        data, confidence_threshold
    )

    try:
        prompt = _build_prompt(data)
        raw = _call_llm(llm_client, prompt, model=model)
        llm_selected = raw.get("selected_state") or data.current_state.value
        if llm_selected not in [s.value for s in data.possible_next_states + [data.current_state]]:
            llm_selected = data.current_state.value
        confidence = float(raw.get("confidence", 0.0))
        confidence = min(confidence, max_confidence)
        status_raw = raw.get("status")
        status = status_raw or pre_status.value
        response_hint = raw.get("response_hint") or pre_hint
        open_items = raw.get("open_items", data.open_items)
        fulfilled_items = raw.get("fulfilled_items", data.fulfilled_items)
        detected_requests = raw.get("detected_requests", data.detected_requests)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "state_selector_llm_failed",
            extra={"correlation_id": correlation_id, "error": type(exc).__name__},
        )
        return StateSelectorOutput(
            selected_state=data.current_state,
            confidence=0.0,
            accepted=False,
            next_state=data.current_state,
            response_hint=(
                "Não foi possível decidir com segurança; "
                "confirme se a solicitação foi atendida ou se há novo pedido."
            ),
            status=pre_status,
            open_items=data.open_items,
            fulfilled_items=data.fulfilled_items,
            detected_requests=data.detected_requests,
        )

    if pre_status != StateSelectorStatus.IN_PROGRESS:
        status = pre_status.value

    accepted = confidence >= confidence_threshold and status in {
        StateSelectorStatus.IN_PROGRESS.value,
        StateSelectorStatus.DONE.value,
    }
    next_state = (
        ConversationState(llm_selected) if accepted else data.current_state
    )
    if not accepted and not response_hint:
        response_hint = (
            "Preciso de confirmação antes de mudar de estado. "
            "Você pode confirmar se a demanda foi atendida ou há outro pedido?"
        )

    output = StateSelectorOutput(
        selected_state=ConversationState(llm_selected),
        confidence=confidence,
        accepted=accepted,
        next_state=next_state,
        response_hint=response_hint,
        status=StateSelectorStatus(status),
        open_items=list(open_items),
        fulfilled_items=list(fulfilled_items),
        detected_requests=list(detected_requests),
    )

    logger.info(
        "state_selector_result",
        extra={
            "correlation_id": correlation_id,
            "current_state": data.current_state.value,
            "selected_state": output.selected_state.value,
            "accepted": output.accepted,
            "confidence": round(output.confidence, 3),
            "status": output.status.value,
        },
    )
    return output
