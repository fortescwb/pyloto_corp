"""Contratos para o gerador de respostas (fase 2B)."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from pyloto_corp.domain.conversation_state import ConversationState, StateSelectorOutput


class ResponseGeneratorInput(BaseModel):
    """Entrada necessária para gerar respostas."""

    last_user_message: str
    day_history: list[dict] = Field(default_factory=list)
    state_decision: StateSelectorOutput
    current_state: ConversationState
    candidate_next_state: ConversationState
    confidence: float
    response_hint: str | None = None

    @model_validator(mode="after")
    def ensure_hint_when_low_confidence(self) -> ResponseGeneratorInput:
        threshold = 0.7
        if self.confidence < threshold and not self.response_hint:
            msg = "response_hint obrigatório quando confiança baixa"
            raise ValueError(msg)
        return self


class ResponseGeneratorOutput(BaseModel):
    """Saída do gerador de respostas."""

    responses: list[str]
    response_style_tags: list[str] = Field(default_factory=list)
    chosen_index: int = 0
    safety_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def ensure_min_responses(self) -> ResponseGeneratorOutput:
        if len(self.responses) < 3:
            msg = "É obrigatório retornar pelo menos 3 respostas"
            raise ValueError(msg)
        if not (0 <= self.chosen_index < len(self.responses)):
            msg = "chosen_index fora do intervalo"
            raise ValueError(msg)
        return self
