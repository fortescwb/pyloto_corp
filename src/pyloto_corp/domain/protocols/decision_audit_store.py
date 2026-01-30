"""Protocolos de domínio para Decision Audit Store."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DecisionAuditStoreProtocol(ABC):
    """Contrato mínimo para armazenamento de auditoria de decisões."""

    @abstractmethod
    def append(self, record: dict[str, Any]) -> None:
        """Append de registro de auditoria."""
