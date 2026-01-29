"""Protocolos de domínio para stores de dedupe.

Interfaces leves (ABCs) dependidas por Application.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class DedupeProtocol(ABC):
    """Contrato mínimo para stores de deduplicação.

    Métodos modelados a partir de `infra.dedupe.DedupeStore` para manter
    compatibilidade com implementações existentes.
    """

    @abstractmethod
    def mark_if_new(self, key: str) -> bool:
        """Marca a chave se for nova (set-if-not-exists).

        Retorna True se chave foi marcada (evento novo), False se já existia.
        """

    @abstractmethod
    def is_duplicate(self, key: str) -> bool:
        """Verifica existência sem marcar."""

    @abstractmethod
    def clear(self, key: str) -> bool:
        """Remove uma chave do store (útil para testes/rollback)."""
