"""Eventos que disparam transições de estado no FSM.

Conforme FSM_LLM_ARCHITECTURE_PYLOTO_CORP.md:
- Eventos representam mudanças detectadas (input do usuário, LLM, timeout, etc.)
- Cada evento + estado atual → próximo estado (tabela de transições)
"""

from __future__ import annotations

from enum import StrEnum


class SessionEvent(StrEnum):
    """11 Eventos canônicos que disparam transições no FSM."""

    # === Input do Usuário ===
    USER_SENT_TEXT = "USER_SENT_TEXT"
    """Usuário enviou mensagem de texto."""

    USER_SENT_MEDIA = "USER_SENT_MEDIA"
    """Usuário enviou mídia (imagem, vídeo, arquivo)."""

    USER_SELECTED_BUTTON = "USER_SELECTED_BUTTON"
    """Usuário clicou em botão interativo."""

    USER_SELECTED_LIST_ITEM = "USER_SELECTED_LIST_ITEM"
    """Usuário selecionou item de lista interativa."""

    # === Processamento Interno ===
    EVENT_DETECTED = "EVENT_DETECTED"
    """LLM #1: Evento do usuário foi classificado (intent + confidence)."""

    RESPONSE_GENERATED = "RESPONSE_GENERATED"
    """LLM #2: Resposta foi gerada com base no evento + contexto."""

    MESSAGE_TYPE_SELECTED = "MESSAGE_TYPE_SELECTED"
    """LLM #3: Tipo de mensagem foi escolhido dinamicamente."""

    # === Desfecho ===
    HUMAN_HANDOFF_READY = "HUMAN_HANDOFF_READY"
    """Lead qualificado e contexto pronto para escalar para humano."""

    SELF_SERVE_COMPLETE = "SELF_SERVE_COMPLETE"
    """Informação entregue; atendimento auto-service completo."""

    EXTERNAL_ROUTE_READY = "EXTERNAL_ROUTE_READY"
    """Cliente será encaminhado para outro canal/WhatsApp."""

    # === Exceções ===
    SESSION_TIMEOUT = "SESSION_TIMEOUT"
    """Sessão expirou por timeout de inatividade."""

    INTERNAL_ERROR = "INTERNAL_ERROR"
    """Falha interna (LLM, storage, validação)."""
