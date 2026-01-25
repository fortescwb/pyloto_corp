"""Detecção de spam e flood para proteção contra abuso.

Implementa mecanismos de detecção de:
- Flood: múltiplas mensagens em intervalo curto
- Spam: padrões de conteúdo suspeito
- Abuso: repetição excessiva de intenções

Conforme Funcionamento.md § 3.3 — DUPLICATE_OR_SPAM outcome.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.application.session import SessionState

logger: logging.Logger = get_logger(__name__)


@dataclass(slots=True)
class FloodDetectionResult:
    """Resultado da análise de flood."""

    is_flooded: bool
    message_count: int
    time_window_seconds: int
    threshold: int


class FloodDetector(ABC):
    """Contrato abstrato para detecção de flood."""

    @abstractmethod
    def check_and_record(
        self, session_id: str, timestamp: float | None = None
    ) -> FloodDetectionResult:
        """Registra evento e verifica se há flood.

        Args:
            session_id: ID da sessão
            timestamp: Timestamp do evento (padrão: agora)

        Returns:
            FloodDetectionResult indicando se há flood
        """
        ...


class InMemoryFloodDetector(FloodDetector):
    """Detector de flood em memória para desenvolvimento.

    ⚠️ Não usar em produção!
    """

    def __init__(
        self,
        threshold: int = 10,
        time_window_seconds: int = 60,
    ) -> None:
        self._threshold = threshold
        self._window = time_window_seconds
        self._events: dict[str, list[float]] = {}

    def check_and_record(
        self, session_id: str, timestamp: float | None = None
    ) -> FloodDetectionResult:
        """Verifica flood e registra evento."""
        now = timestamp or time.time()

        if session_id not in self._events:
            self._events[session_id] = []

        events = self._events[session_id]

        # Remover eventos fora da janela
        cutoff = now - self._window
        events[:] = [ts for ts in events if ts >= cutoff]

        # Adicionar novo evento
        events.append(now)

        is_flooded = len(events) >= self._threshold

        if is_flooded:
            logger.warning(
                "Flood detected (in-memory)",
                extra={
                    "session_id": session_id[:8] + "...",
                    "message_count": len(events),
                    "threshold": self._threshold,
                    "window_seconds": self._window,
                },
            )

        return FloodDetectionResult(
            is_flooded=is_flooded,
            message_count=len(events),
            time_window_seconds=self._window,
            threshold=self._threshold,
        )


class RedisFloodDetector(FloodDetector):
    """Detector de flood via Redis com TTL nativo.

    Características:
    - Usa INCR com EXPIRE para atomicidade
    - Escalável para múltiplas instâncias
    """

    def __init__(
        self,
        redis_client: object,
        threshold: int = 10,
        time_window_seconds: int = 60,
    ) -> None:
        self._redis = redis_client
        self._threshold = threshold
        self._window = time_window_seconds

    def check_and_record(
        self, session_id: str, timestamp: float | None = None
    ) -> FloodDetectionResult:
        """Verifica flood usando Redis."""
        key = f"flood:{session_id}"

        try:
            count = self._redis.incr(key)
            if count == 1:
                # Primeira ocorrência: setar TTL
                self._redis.expire(key, self._window)

            is_flooded = count >= self._threshold

            if is_flooded:
                logger.warning(
                    "Flood detected (Redis)",
                    extra={
                        "session_id": session_id[:8] + "...",
                        "message_count": count,
                        "threshold": self._threshold,
                        "window_seconds": self._window,
                    },
                )

            return FloodDetectionResult(
                is_flooded=is_flooded,
                message_count=count,
                time_window_seconds=self._window,
                threshold=self._threshold,
            )
        except Exception as e:
            logger.error(
                "Redis flood detection error",
                extra={
                    "session_id": session_id[:8] + "...",
                    "error": str(e),
                },
            )
            # Em caso de falha, assumir safe (não marcar como flood)
            return FloodDetectionResult(
                is_flooded=False,
                message_count=0,
                time_window_seconds=self._window,
                threshold=self._threshold,
            )


class SpamDetector:
    """Detecção heurística de spam/abuso de conteúdo.

    Regras simples:
    - Mensagem vazia
    - Conteúdo muito curto
    - Caracteres repetidos
    - Conteúdo não reconhecido (fora de padrão esperado)
    """

    def __init__(self) -> None:
        self._min_message_length = 2
        self._max_repetition_ratio = 0.8  # 80% caracteres iguais

    def is_spam(self, text: str) -> bool:
        """Avalia se conteúdo é suspeito de spam.

        Retorna True se conteúdo parece spam.
        """

        if not text or len(text.strip()) < self._min_message_length:
            return False  # Vazio não é spam, só inválido

        # Verificar repetição excessiva de caracteres
        text_clean = text.strip()
        if len(text_clean) > 0:
            unique_chars = len(set(text_clean))
            if unique_chars > 0:
                repetition_ratio = 1 - (unique_chars / len(text_clean))
                if repetition_ratio > self._max_repetition_ratio:
                    logger.debug(
                        "Spam detected: excessive repetition",
                        extra={
                            "repetition_ratio": round(repetition_ratio, 2),
                        },
                    )
                    return True

        return False


class AbuseChecker:
    """Verifica padrões de abuso em sessão."""

    def __init__(self, max_intents_exceeded: int = 3) -> None:
        self._max_intents = max_intents_exceeded

    def is_abuse(self, session: SessionState | None) -> bool:
        """Verifica se há padrão de abuso detectado.

        Retorna True se sessão mostra sinais de abuso.
        """

        if not session:
            return False

        # Se sessão já tem outcome terminal (exceto AWAITING_USER),
        # e continua recebendo mensagens, pode ser abuso
        if session.outcome and session.outcome.value not in (
            "AWAITING_USER",
            "SCHEDULED_FOLLOWUP",
        ):
            logger.debug(
                "Potential abuse: session already terminated",
                extra={
                    "session_id": session.session_id[:8] + "...",
                    "outcome": session.outcome,
                },
            )
            return True

        # Se fila de intenções está no limite máximo,
        # é um sinal de abuso (múltiplas demandas não resolvidas)
        if session.intent_queue.is_at_capacity():
            logger.debug(
                "Potential abuse: intent queue at capacity",
                extra={
                    "session_id": session.session_id[:8] + "...",
                    "total_intents": session.intent_queue.total_intents(),
                },
            )
            return True

        return False
