"""Formatação de resposta final — aplicação de prefixos, masking, etc."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def apply_otto_intro_if_first(reply_text: str | None, is_first: bool) -> str | None:
    """Aplica prefixo do Otto se for primeira mensagem na sessão.

    Args:
        reply_text: Texto da resposta (pode ser None)
        is_first: Se é a primeira mensagem da sessão

    Returns:
        Texto com prefixo aplicado, ou None se reply_text for None
    """
    if not is_first or reply_text is None:
        return reply_text

    try:
        from pyloto_corp.domain.constants.otto import OTTO_INTRO_TEXT

        if reply_text.strip().startswith(OTTO_INTRO_TEXT):
            return reply_text
        return f"{OTTO_INTRO_TEXT}\n\n{reply_text}"
    except Exception:
        logger = logging.getLogger(__name__)
        logger.exception("otto_prefix_application_failed")
        return reply_text
