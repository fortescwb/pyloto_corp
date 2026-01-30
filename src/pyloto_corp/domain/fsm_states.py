"""Máquina de Estados Finitos (FSM) para conversa de atendimento.

Estados canônicos do fluxo de atendimento inicial com histórico e transições válidas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)


class ConversationState(str, Enum):
    """Estados válidos de conversa."""

    # Inicial
    INIT = "INIT"

    # Fase de identificação
    IDENTIFYING = "IDENTIFYING"

    # Fase de entendimento de intenção
    UNDERSTANDING_INTENT = "UNDERSTANDING_INTENT"

    # Processando com LLM
    PROCESSING = "PROCESSING"

    # Gerando resposta
    GENERATING_RESPONSE = "GENERATING_RESPONSE"

    # Selecionando tipo de mensagem
    SELECTING_MESSAGE_TYPE = "SELECTING_MESSAGE_TYPE"

    # Aguardando confirmação/resposta do usuário
    AWAITING_USER = "AWAITING_USER"

    # Handoff para humano
    ESCALATING = "ESCALATING"

    # Terminais
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SPAM = "SPAM"


@dataclass
class StateTransition:
    """Representa uma transição válida de estado."""

    from_state: ConversationState
    to_state: ConversationState
    trigger: str  # O que causou a transição (ex: "user_message", "timeout", "error")
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    confidence: float = 1.0  # 0-1, confiança na transição


class FSMStateMachine:
    """Máquina de estados com histórico e validação de transições."""

    # Estados iniciais possíveis
    INITIAL_STATES = {ConversationState.INIT}

    # Estados finais (não podem transicionar)
    TERMINAL_STATES = {
        ConversationState.COMPLETED,
        ConversationState.FAILED,
        ConversationState.SPAM,
    }

    # Transições válidas (from → allowed_to)
    VALID_TRANSITIONS = {
        ConversationState.INIT: {
            ConversationState.IDENTIFYING,
            ConversationState.SPAM,
        },
        ConversationState.IDENTIFYING: {
            ConversationState.UNDERSTANDING_INTENT,
            ConversationState.SPAM,
        },
        ConversationState.UNDERSTANDING_INTENT: {
            ConversationState.PROCESSING,
            ConversationState.ESCALATING,
            ConversationState.SPAM,
        },
        ConversationState.PROCESSING: {
            ConversationState.GENERATING_RESPONSE,
            ConversationState.ESCALATING,
            ConversationState.FAILED,
        },
        ConversationState.GENERATING_RESPONSE: {
            ConversationState.SELECTING_MESSAGE_TYPE,
            ConversationState.ESCALATING,
            ConversationState.FAILED,
        },
        ConversationState.SELECTING_MESSAGE_TYPE: {
            ConversationState.AWAITING_USER,
            ConversationState.COMPLETED,
            ConversationState.FAILED,
        },
        ConversationState.AWAITING_USER: {
            ConversationState.UNDERSTANDING_INTENT,  # Novo input
            ConversationState.COMPLETED,
            ConversationState.ESCALATING,
        },
        ConversationState.ESCALATING: {
            ConversationState.COMPLETED,
            ConversationState.FAILED,
        },
        ConversationState.COMPLETED: set(),
        ConversationState.FAILED: set(),
        ConversationState.SPAM: set(),
    }

    def __init__(self) -> None:
        """Inicializa FSM."""
        self.current_state = ConversationState.INIT
        self.history: list[StateTransition] = []
        self.transition_count = 0

    def can_transition_to(self, target_state: ConversationState) -> bool:
        """Verifica se transição é válida."""
        if self.current_state in self.TERMINAL_STATES:
            logger.warning(
                "cannot_transition_from_terminal",
                extra={"current": self.current_state, "target": target_state},
            )
            return False

        valid_targets = self.VALID_TRANSITIONS.get(self.current_state, set())
        return target_state in valid_targets

    def transition(
        self,
        target_state: ConversationState,
        trigger: str,
        metadata: dict[str, Any] | None = None,
        confidence: float = 1.0,
    ) -> bool:
        """Realiza transição de estado com validação e histórico.

        Args:
            target_state: Estado destino
            trigger: O que causou a transição
            metadata: Informações adicionais da transição
            confidence: Confiança na transição (0-1)

        Returns:
            True se transição bem-sucedida, False caso contrário
        """
        if not self.can_transition_to(target_state):
            logger.warning(
                "invalid_state_transition",
                extra={
                    "from": self.current_state,
                    "to": target_state,
                    "trigger": trigger,
                },
            )
            return False

        trans = StateTransition(
            from_state=self.current_state,
            to_state=target_state,
            trigger=trigger,
            metadata=metadata or {},
            confidence=confidence,
        )

        self.history.append(trans)
        self.current_state = target_state
        self.transition_count += 1

        logger.debug(
            "state_transition",
            extra={
                "from": trans.from_state,
                "to": trans.to_state,
                "trigger": trigger,
                "count": self.transition_count,
            },
        )

        return True

    def get_history(self) -> list[StateTransition]:
        """Retorna histórico de transições."""
        return self.history.copy()

    def get_state_summary(self) -> dict[str, Any]:
        """Retorna resumo do estado atual."""
        return {
            "current_state": self.current_state,
            "transition_count": self.transition_count,
            "is_terminal": self.current_state in self.TERMINAL_STATES,
            "history_length": len(self.history),
            "last_transition": (self.history[-1] if self.history else None),
        }

    def reset(self) -> None:
        """Reseta FSM para estado inicial."""
        self.current_state = ConversationState.INIT
        self.history.clear()
        self.transition_count = 0
