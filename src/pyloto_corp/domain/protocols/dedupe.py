"""Protocolos de domínio para stores de dedupe.

Interfaces leves (ABCs) dependidas por Application.

Nota: PR-07 introduz o método `seen(key, ttl)` como API canônica, que é
atômico (verifica+marca). Para manter compatibilidade com código legadoo,
métodos auxiliares podem existir nas implementações.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class DedupeProtocol(ABC):
    """Contrato mínimo para stores de deduplicação.

    Método canônico:
    - seen(key: str, ttl: int) -> bool
      Retorna True se a chave já foi vista (duplicado). Se não vista, marca-a
      com TTL e retorna False.
    """

    @abstractmethod
    def seen(self, key: str, ttl: int) -> bool:
        """Verifica e marca a chave de forma atômica.

        Args:
            key: Chave única (ex.: message_id ou hash)
            ttl: TTL em segundos

        Returns:
            True se já foi vista (duplicado); False se foi marcada agora (novo).
        """
