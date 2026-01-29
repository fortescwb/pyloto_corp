"""Gerador de respostas usando hint do state selector."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from pyloto_corp.domain.response_generator import (
    ResponseGeneratorInput,
    ResponseGeneratorOutput,
)
from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)


def _deterministic_fallback(
    data: ResponseGeneratorInput, safety_notes: list[str]
) -> ResponseGeneratorOutput:
    """Fallback determinístico sempre produzindo 3 respostas."""
    base = "Estou aqui para ajudar. "
    if data.response_hint:
        base += data.response_hint + " "
    responses = [
        f"{base}Você pode confirmar se resolvemos o que precisa?",
        f"{base}Quer que eu finalize ou há outro pedido?",
        f"{base}Se preferir, posso conectar com um humano.",
    ]
    return ResponseGeneratorOutput(
        responses=responses,
        response_style_tags=["neutra", "curta"],
        chosen_index=0,
        safety_notes=safety_notes,
    )


def _build_prompt(data: ResponseGeneratorInput) -> str:
    """Monta prompt com schema JSON."""
    schema = {
        "type": "object",
        "properties": {
            "responses": {"type": "array", "items": {"type": "string"}, "minItems": 3},
            "response_style_tags": {"type": "array", "items": {"type": "string"}},
            "chosen_index": {"type": "integer", "minimum": 0},
            "safety_notes": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["responses", "chosen_index"],
    }
    hint = data.response_hint or ""
    intent = "confirmação" if hint else "responder objetivamente"
    return (
        "Gere respostas institucionais Pyloto em PT-BR. "
        f"Contexto: estado atual {data.current_state.value}, "
        f"próximo {data.candidate_next_state.value}. "
        f"Confiança: {data.confidence}. Hint: {hint}. Objetivo: {intent}. "
        f"Última mensagem: {data.last_user_message}. "
        f"Responda somente JSON que siga este schema: {json.dumps(schema)}"
    )


def _call_llm(
    llm_client: Any, prompt: str, model: str | None, timeout: float | None
) -> Mapping[str, Any]:
    """Chamada resiliente ao LLM; espera dict."""
    if hasattr(llm_client, "complete"):
        return llm_client.complete(prompt, model=model, timeout=timeout)
    if hasattr(llm_client, "chat") and hasattr(llm_client.chat, "completions"):
        response = llm_client.chat.completions.create(
            model=model or getattr(llm_client, "_model", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=220,
            timeout=timeout,
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
    if callable(llm_client):
        return llm_client(prompt)
    raise RuntimeError("llm_client incompatível")


def generate_response_options(
    data: ResponseGeneratorInput,
    llm_client: Any,
    *,
    correlation_id: str,
    model: str | None,
    timeout_seconds: float | None,
    min_responses: int = 3,
) -> ResponseGeneratorOutput:
    """Gera opções de resposta; nunca retorna menos de 3 itens."""
    safety_notes = ["não expor PII", "não repetir número do cliente", "tom neutro"]
    try:
        prompt = _build_prompt(data)
        raw = _call_llm(llm_client, prompt, model, timeout_seconds)
        responses = raw.get("responses") or []
        if len(responses) < min_responses:
            raise ValueError("llm_responses_insufficient")
        chosen_index = int(raw.get("chosen_index", 0))
        tags = raw.get("response_style_tags") or []
        notes = raw.get("safety_notes") or safety_notes
        output = ResponseGeneratorOutput(
            responses=responses[: max(len(responses), min_responses)],
            response_style_tags=list(tags),
            chosen_index=chosen_index,
            safety_notes=list(notes),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "response_generator_llm_failed",
            extra={
                "correlation_id": correlation_id,
                "error": type(exc).__name__,
                "state": data.current_state.value,
                "next_state": data.candidate_next_state.value,
                "had_hint": bool(data.response_hint),
            },
        )
        output = _deterministic_fallback(data, safety_notes)

    logger.info(
        "response_generator_result",
        extra={
            "correlation_id": correlation_id,
            "state": data.current_state.value,
            "next_state": data.candidate_next_state.value,
            "status": data.state_decision.status.value,
            "confidence": round(data.confidence, 3),
            "had_hint": bool(data.response_hint),
        },
    )
    return output
