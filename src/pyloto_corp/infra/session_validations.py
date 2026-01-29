"""Validações de sessão antes de persistir em qualquer SessionStore."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyloto_corp.domain.enums import Outcome
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.application.session import SessionState


logger = get_logger(__name__)


def ensure_terminal_outcome(session: SessionState) -> Outcome:
    """Garante outcome canônico antes de salvar sessão.

    Sessões sem outcome definido são falha de produto. Para evitar persistência
    ambígua, normalizamos para um outcome terminal seguro ou padronizamos
    qualquer valor inválido como FAILED_INTERNAL.
    """

    outcome = session.outcome

    if outcome is None:
        logger.error(
            "session_outcome_missing",
            extra={"session_id": session.session_id[:8]},
        )
        session.outcome = Outcome.FAILED_INTERNAL
        return session.outcome

    try:
        session.outcome = Outcome(outcome)
        return session.outcome
    except ValueError:
        logger.error(
            "session_outcome_invalid",
            extra={
                "session_id": session.session_id[:8],
                "outcome": str(outcome),
            },
        )
        session.outcome = Outcome.FAILED_INTERNAL
        return session.outcome
