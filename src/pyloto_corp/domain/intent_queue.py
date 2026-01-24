"""Fila leve de intenções (máximo 3 por sessão)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from pyloto_corp.domain.enums import Intent


@dataclass(slots=True)
class IntentItem:
    """Item de intenção com metadados mínimos para contenção de contexto."""

    intent: Intent
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    confidence: float | None = None


@dataclass(slots=True)
class IntentQueue:
    """Fila de intenções com limite rígido (3)."""

    active_intent: Intent | None = None
    queued: list[IntentItem] = field(default_factory=list)
    max_items: int = 3

    def add_intent(self, intent: Intent, confidence: float | None = None) -> bool:
        """Adiciona intenção se houver capacidade.

        Retorna True se adicionada, False se exceder o limite.
        """

        if self.active_intent is None:
            self.active_intent = intent
            return True

        if len(self.queued) >= self.max_items - 1:
            return False

        self.queued.append(IntentItem(intent=intent, confidence=confidence))
        return True

    def pop_next(self) -> Intent | None:
        """Promove a próxima intenção para ativa."""

        if not self.queued:
            self.active_intent = None
            return None

        next_item = self.queued.pop(0)
        self.active_intent = next_item.intent
        return self.active_intent
