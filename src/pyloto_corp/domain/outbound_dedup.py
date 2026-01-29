"""Contrato de Deduplicação Outbound — Protocolo e Tipos.

Responsabilidades:
- Definir protocolo abstrato para store de idempotência
- Garantir contrato entre Application e Infra
- Definir DTOs de domínio

Conforme regras_e_padroes.md (contratos explícitos, SRP).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class DedupeResult:
    """Resultado de verificação de deduplicação."""

    is_duplicate: bool
    original_message_id: str | None = None
    original_timestamp: datetime | None = None
    status: str | None = None  # pending | sent | failed
    error: str | None = None


class OutboundDedupeError(Exception):
    """Erro em operação de deduplicação outbound."""

    pass


class OutboundDedupeStore(ABC):
    """Contrato abstrato para deduplicação de mensagens outbound.

    Responsabilidade: Verificar e persistir idempotency_keys com TTL.

    Cada mensagem outbound deve receber um idempotency_key único gerado a partir de:
    - recipient_id
    - conteúdo da mensagem (hash)
    - timestamp (janela)

    Isso evita envio duplicado mesmo em retries ou falhas de rede.
    """

    # TTL padrão: 24 horas (cobre retries e reconciliação)
    DEFAULT_TTL_SECONDS = 86400

    @abstractmethod
    def check_and_mark(
        self,
        idempotency_key: str,
        message_id: str,
        ttl_seconds: int | None = None,
    ) -> DedupeResult:
        """Verifica se já foi enviado e marca como enviado.

        Atomicidade é obrigatória (race condition safe).

        Args:
            idempotency_key: Chave de idempotência
            message_id: ID da mensagem sendo enviada
            ttl_seconds: TTL para expiração (default: DEFAULT_TTL_SECONDS)

        Returns:
            DedupeResult indicando se é duplicata

        Raises:
            OutboundDedupeError: Em modo fail-closed quando backend indisponível
        """
        ...

    @abstractmethod
    def is_sent(self, idempotency_key: str) -> bool:
        """Verifica se mensagem já foi enviada.

        Args:
            idempotency_key: Chave de idempotência

        Returns:
            True se já foi enviada e não expirou

        Raises:
            OutboundDedupeError: Em modo fail-closed
        """
        ...

    @abstractmethod
    def mark_failed(
        self,
        idempotency_key: str,
        error: str | None = None,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Marca envio como falhado (persistente).

        Args:
            idempotency_key: Chave de idempotência
            error: Mensagem de erro para auditoria
            ttl_seconds: TTL para expiração

        Returns:
            True se marcado, False se já havia status anterior

        Raises:
            OutboundDedupeError: Em modo fail-closed
        """
        ...

    @abstractmethod
    def get_status(self, idempotency_key: str) -> str | None:
        """Obtém status atual do envio (pending/sent/failed).

        Returns:
            Status string ou None se inexistente/expirado
        """
        ...

    @abstractmethod
    def mark_sent(
        self,
        idempotency_key: str,
        message_id: str,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Marca mensagem como enviada.

        Args:
            idempotency_key: Chave de idempotência
            message_id: ID da mensagem
            ttl_seconds: TTL para expiração

        Returns:
            True se marcou com sucesso, False se já existia

        Raises:
            OutboundDedupeError: Em modo fail-closed
        """
        ...
