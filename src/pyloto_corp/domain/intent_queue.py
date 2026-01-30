"""Fila leve de intenções com enforcement de limite (máximo 3 por sessão).

Conforme Funcionamento.md § 3.2 — Multi-intent:
- Máximo 3 intenções por sessão
- Apenas uma intenção ativa por vez
- Ao atingir o limite: SCHEDULED_FOLLOWUP ou HANDOFF_HUMAN (se lead comercial)
"""

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
    """Fila de intenções com enforcement de limite rígido (máx 3).

    Invariantes:
    - Apenas uma intenção ativa por vez (active_intent)
    - Demais intenções na fila (queued)
    - Limite total = max_items (padrão: 3)
    - add_intent retorna False se exceder o limite
    """

    active_intent: Intent | None = None
    queued: list[IntentItem] = field(default_factory=list)
    max_items: int = 3

    def add_intent(self, intent: Intent, confidence: float | None = None) -> bool:
        """Adiciona intenção se houver capacidade.

        Retorna True se adicionada, False se exceder limite.

        Regra:
        - Se active_intent é None: torna ativa
        - Se fila tem espaço (<max_items-1): adiciona à fila
        - Caso contrário: recusa (returns False)
        """

        if self.active_intent is None:
            self.active_intent = intent
            return True

        if len(self.queued) >= self.max_items - 1:
            return False

        self.queued.append(IntentItem(intent=intent, confidence=confidence))
        return True

    def is_at_capacity(self) -> bool:
        """Verifica se a fila está no limite máximo."""
        total = (1 if self.active_intent else 0) + len(self.queued)
        return total >= self.max_items

    def total_intents(self) -> int:
        """Retorna total de intenções (ativa + fila)."""
        return (1 if self.active_intent else 0) + len(self.queued)

    def pop_next(self) -> Intent | None:
        """Promove a próxima intenção para ativa.

        Retorna a intenção promovida ou None se fila vazia.
        """

        if not self.queued:
            self.active_intent = None
            return None

        next_item = self.queued.pop(0)
        self.active_intent = next_item.intent
        return self.active_intent

    def has_pending(self) -> bool:
        """Verifica se há intenções pendentes na fila."""
        return bool(self.queued)

    def clear(self) -> None:
        """Limpa todas as intenções (para reset de sessão)."""
        self.active_intent = None
        self.queued.clear()
