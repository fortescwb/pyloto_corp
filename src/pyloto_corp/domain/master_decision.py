"""Contratos para o decisor mestre (LLM3)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from pyloto_corp.domain.conversation_state import ConversationState, StateSelectorOutput
from pyloto_corp.domain.enums import MessageType
from pyloto_corp.domain.response_generator import ResponseGeneratorOutput


class MasterDecisionInput(BaseModel):
    """Entrada agregada para o decisor mestre."""

    last_user_message: str
    day_history: list[dict] = Field(default_factory=list)
    state_decision: StateSelectorOutput
    response_options: ResponseGeneratorOutput
    current_state: ConversationState
    correlation_id: str


class MasterDecisionOutput(BaseModel):
    """Saída executável do decisor mestre."""

    final_state: ConversationState
    apply_state: bool = True
    selected_response_index: int
    selected_response_text: str
    message_type: MessageType = MessageType.TEXT
    overall_confidence: float
    reason: str
    decision_trace: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_rules(self) -> MasterDecisionOutput:
        if not 0.0 <= self.overall_confidence <= 1.0:
            msg = "overall_confidence deve estar entre 0 e 1"
            raise ValueError(msg)
        if not self.reason or not self.reason.strip():
            msg = "reason é obrigatório"
            raise ValueError(msg)
        responses = self.decision_trace.get("responses")
        if responses:
            if not (0 <= self.selected_response_index < len(responses)):
                msg = "selected_response_index fora do range"
                raise ValueError(msg)
            if responses[self.selected_response_index] != self.selected_response_text:
                msg = "selected_response_text deve corresponder ao índice escolhido"
                raise ValueError(msg)
        return self
