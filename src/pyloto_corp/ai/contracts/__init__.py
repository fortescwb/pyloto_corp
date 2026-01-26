"""Contratos Pydantic para os 3 pontos de LLM."""

from pyloto_corp.ai.contracts.event_detection import (
    EventDetectionRequest,
    EventDetectionResult,
)
from pyloto_corp.ai.contracts.message_type_selection import (
    MessageTypeSelectionRequest,
    MessageTypeSelectionResult,
)
from pyloto_corp.ai.contracts.response_generation import (
    ResponseGenerationRequest,
    ResponseGenerationResult,
    ResponseOption,
)

__all__ = [
    "EventDetectionRequest",
    "EventDetectionResult",
    "ResponseGenerationRequest",
    "ResponseGenerationResult",
    "ResponseOption",
    "MessageTypeSelectionRequest",
    "MessageTypeSelectionResult",
]
