"""Contratos do seletor de estado (LLM #1)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class ConversationState(str, Enum):
    """Estados conversacionais canônicos."""

    INIT = "INIT"
    AWAITING_USER = "AWAITING_USER"
    HANDOFF_HUMAN = "HANDOFF_HUMAN"
    SELF_SERVE_INFO = "SELF_SERVE_INFO"
    ROUTE_EXTERNAL = "ROUTE_EXTERNAL"
    SCHEDULED_FOLLOWUP = "SCHEDULED_FOLLOWUP"
    DUPLICATE_OR_SPAM = "DUPLICATE_OR_SPAM"
    FAILED_INTERNAL = "FAILED_INTERNAL"


class StateSelectorStatus(str, Enum):
    """Status da decisão."""

    DONE = "done"
    IN_PROGRESS = "in_progress"
    NEEDS_CLARIFICATION = "needs_clarification"
    NEW_REQUEST_DETECTED = "new_request_detected"


class StateSelectorInput(BaseModel):
    """Entrada para o seletor de estado."""

    current_state: ConversationState
    possible_next_states: list[ConversationState]
    message_text: str = ""
    history_summary: list[str] = Field(default_factory=list)
    open_items: list[str] = Field(default_factory=list)
    fulfilled_items: list[str] = Field(default_factory=list)
    detected_requests: list[str] = Field(default_factory=list)

    @field_validator("possible_next_states")
    @classmethod
    def ensure_non_empty(cls, value: list[ConversationState]) -> list[ConversationState]:
        if not value:
            msg = "possible_next_states não pode ser vazio"
            raise ValueError(msg)
        return value


class StateSelectorOutput(BaseModel):
    """Saída padronizada do seletor de estado."""

    selected_state: ConversationState
    confidence: float
    accepted: bool
    next_state: ConversationState
    response_hint: str | None = None
    status: StateSelectorStatus = StateSelectorStatus.IN_PROGRESS
    open_items: list[str] = Field(default_factory=list)
    fulfilled_items: list[str] = Field(default_factory=list)
    detected_requests: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_business_rules(self) -> StateSelectorOutput:
        """Aplica regras de aceitação."""
        if not 0.0 <= self.confidence <= 1.0:
            msg = "confidence deve estar entre 0 e 1"
            raise ValueError(msg)

        if self.accepted and self.confidence < 0.7:
            msg = "accepted true requer confidence >= 0.7"
            raise ValueError(msg)

        if not self.accepted:
            if not self.response_hint or not self.response_hint.strip():
                msg = "response_hint é obrigatório quando accepted=false"
                raise ValueError(msg)
            self.next_state = self.next_state or self.selected_state

        return self
