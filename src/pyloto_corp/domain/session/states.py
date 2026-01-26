"""Estados canônicos de uma sessão de atendimento initial.

Conforme Funcionamento.md § 3.1–3.4:
- Toda sessão termina em exatamente 1 outcome terminal
- Estados definem a posição no fluxo de atendimento
- Transições são explícitas (FSM)
"""

from __future__ import annotations

from enum import StrEnum


class SessionState(StrEnum):
    """10 Estados canônicos de uma sessão de atendimento."""

    # === Entrada ===
    INITIAL = "INITIAL"
    """Sessão iniciada, aguardando primeira mensagem válida."""

    # === Processamento ===
    TRIAGE = "TRIAGE"
    """Classificação de intenção em andamento."""

    COLLECTING_INFO = "COLLECTING_INFO"
    """Coleta estruturada de dados (mínimo obrigatório por fluxo)."""

    GENERATING_RESPONSE = "GENERATING_RESPONSE"
    """Preparando resposta contextualizada."""

    # === Outcomes Terminais (encerramento) ===
    HANDOFF_HUMAN = "HANDOFF_HUMAN"
    """Lead qualificado, pronto para continuidade humana."""

    SELF_SERVE_INFO = "SELF_SERVE_INFO"
    """Cliente atendido apenas com informação; encerrada."""

    ROUTE_EXTERNAL = "ROUTE_EXTERNAL"
    """Cliente encaminhado para outro canal/WhatsApp; encerrada."""

    SCHEDULED_FOLLOWUP = "SCHEDULED_FOLLOWUP"
    """Atendimento encerrado com follow-up agendado."""

    # === Exceções/Erros ===
    TIMEOUT = "TIMEOUT"
    """Sessão expirou por inatividade do usuário (timeout)."""

    ERROR = "ERROR"
    """Falha interna ou de integração; sessão encerrada."""


# Constantes auxiliares
TERMINAL_STATES = frozenset({
    SessionState.HANDOFF_HUMAN,
    SessionState.SELF_SERVE_INFO,
    SessionState.ROUTE_EXTERNAL,
    SessionState.SCHEDULED_FOLLOWUP,
    SessionState.TIMEOUT,
    SessionState.ERROR,
})
"""Estados que encerram a sessão (sem transições posteriores)."""

NON_TERMINAL_STATES = frozenset({
    s for s in SessionState if s not in TERMINAL_STATES
})
"""Estados que permitem transições posteriores."""
