"""Validação de sessão — abuse, intent capacity, etc."""

import logging
from typing import TYPE_CHECKING

from pyloto_corp.domain.enums import Outcome

if TYPE_CHECKING:
    from pyloto_corp.application.session import SessionState
    from pyloto_corp.domain.abuse_detection import AbuseChecker, FloodDetector, SpamDetector


def check_session_validation(
    message,
    session: "SessionState",
    flood_detector: "FloodDetector | None",
    spam_detector: "SpamDetector",
    abuse_checker: "AbuseChecker",
) -> tuple[bool, Outcome | None]:
    """Valida sessão (flood, spam, abuso, intent capacity).

    Returns:
        (is_valid, outcome): (True, None) se válido, ou (False, Outcome) se rejeitado
    """
    logger = logging.getLogger(__name__)

    # Verificar flood
    if flood_detector:
        flood_result = flood_detector.check_and_record(session.session_id)
        if flood_result.is_flooded:
            logger.warning(
                "Message rejected: flood",
                extra={"session_id": session.session_id[:8]},
            )
            return False, Outcome.DUPLICATE_OR_SPAM

    # Verificar spam
    if spam_detector.is_spam(message.text or ""):
        logger.warning(
            "Message rejected: spam",
            extra={"session_id": session.session_id[:8]},
        )
        return False, Outcome.DUPLICATE_OR_SPAM

    # Verificar abuso
    if abuse_checker.is_abuse(session):
        logger.warning(
            "Message rejected: abuse",
            extra={"session_id": session.session_id[:8]},
        )
        return False, Outcome.DUPLICATE_OR_SPAM

    # Verificar intent capacity
    if session.intent_queue.is_at_capacity():
        logger.info(
            "Session at max intents",
            extra={"session_id": session.session_id[:8]},
        )
        return False, Outcome.SCHEDULED_FOLLOWUP

    return True, None
