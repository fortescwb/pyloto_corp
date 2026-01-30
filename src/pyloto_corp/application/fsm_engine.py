"""Engine FSM puro — dispatcher determinístico sem side effects.

Conforme FSM_LLM_ARCHITECTURE_PYLOTO_CORP.md § 2.2 e regras_e_padroes.md:
- Puro: entrada → output sem modificar estado externo
- Testável: resultado é determinístico dado entrada
- Auditável: logs estruturados sem PII
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pyloto_corp.domain.session.events import SessionEvent
from pyloto_corp.domain.session.states import TERMINAL_STATES, SessionState
from pyloto_corp.domain.session.transitions import validate_transition
from pyloto_corp.observability.logging import get_logger

logger: logging.Logger = get_logger(__name__)


@dataclass(slots=True)
class FSMDispatchResult:
    """Resultado da execução do dispatcher FSM.

    Contém:
    - next_state: próximo estado (ou None se inválido)
    - valid: se a transição foi válida
    - error: mensagem de erro (se inválido)
    - actions: lista de ações a executar após transição
    """

    next_state: SessionState | None = None
    valid: bool = False
    error: str | None = None
    actions: list[str] = field(default_factory=list)

    def is_terminal(self) -> bool:
        """True se next_state é terminal."""
        return self.next_state in TERMINAL_STATES if self.next_state else False


class FSMEngine:
    """Engine FSM — dispatcher puro e determinístico."""

    def __init__(self) -> None:
        pass

    def dispatch(
        self,
        current_state: SessionState,
        event: SessionEvent,
        payload: dict[str, Any] | None = None,
    ) -> FSMDispatchResult:
        """Executa transição FSM.

        Args:
            current_state: estado atual
            event: evento disparador
            payload: dados contextuais (não modificado)

        Returns:
            FSMDispatchResult com next_state válido ou erro

        Contrato:
        - Nunca lança exceção
        - Sempre retorna FSMDispatchResult
        - Output é determinístico
        - Sem side effects
        """
        # Validar transição
        is_valid, next_state, error = validate_transition(current_state, event)

        if not is_valid:
            logger.debug(
                "FSM transition invalid",
                extra={
                    "current_state": current_state,
                    "event": event,
                    "error": error,
                },
            )
            return FSMDispatchResult(next_state=None, valid=False, error=error, actions=[])

        # Transição válida: determinar ações
        actions = self._determine_actions(current_state, event, next_state)

        logger.debug(
            "FSM transition valid",
            extra={
                "current_state": current_state,
                "event": event,
                "next_state": next_state,
                "actions_count": len(actions),
            },
        )

        return FSMDispatchResult(
            next_state=next_state,
            valid=True,
            error=None,
            actions=actions,
        )

    def _determine_actions(
        self,
        current_state: SessionState,
        event: SessionEvent,
        next_state: SessionState,
    ) -> list[str]:
        """Determina ações associadas à transição.

        Sem side effects; apenas logic pura.
        Ações são strings indicando o que fazer depois.
        """
        actions: list[str] = []

        # Ações por padrão de transição
        if event == SessionEvent.USER_SENT_TEXT:
            actions.append("DETECT_EVENT")
            actions.append("VALIDATE_INPUT")

        if event == SessionEvent.EVENT_DETECTED:
            actions.append("CLASSIFY_INTENT")

        if event == SessionEvent.RESPONSE_GENERATED:
            actions.append("PREPARE_RESPONSE")

        if event == SessionEvent.MESSAGE_TYPE_SELECTED:
            actions.append("SEND_MESSAGE")

        # Ações finais (estados terminais)
        if next_state in TERMINAL_STATES:
            actions.append("PERSIST_SESSION")
            actions.append("EMIT_OUTCOME")

        return actions
