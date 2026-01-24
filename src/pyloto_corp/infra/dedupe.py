"""Dedupe e idempotência (esqueleto)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class DedupeStore(Protocol):
    """Contrato mínimo de dedupe."""

    def check_and_mark(self, key: str) -> bool:
        """Retorna True se a chave já foi processada."""


@dataclass(slots=True)
class InMemoryDedupeStore:
    """Dedupe em memória (apenas dev/teste).

    TODO: substituir por Redis em ambiente real.
    """

    _seen: set[str] = field(default_factory=set)

    def check_and_mark(self, key: str) -> bool:
        if key in self._seen:
            return True
        self._seen.add(key)
        return False


class RedisDedupeStore:
    """Placeholder para Redis.

    TODO: implementar com fail-closed em staging/prod.
    """

    def __init__(self, _dsn: str) -> None:
        self._dsn = _dsn

    def check_and_mark(self, _key: str) -> bool:
        raise NotImplementedError("RedisDedupeStore ainda não implementado")
