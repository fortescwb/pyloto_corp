"""Modelo de perfil do usuário (dados coletados controlados).

Conforme regras_e_padroes.md:
- Zero-trust: validação rigorosa de PII
- LGPD: suporte a direito ao esquecimento
- Logs estruturados sem expor dados pessoais
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, Field


class QualificationLevel(str, Enum):
    """Nível de qualificação do lead."""

    COLD = "cold"  # Lead frio, apenas contato inicial
    WARM = "warm"  # Lead morno, interesse demonstrado
    HOT = "hot"  # Lead quente, pronto para conversão
    QUALIFIED = "qualified"  # Lead qualificado (handoff humano)


class UserProfile(BaseModel):
    """Perfil do usuário com PII restrita.

    Campos sensíveis (PII):
    - phone_e164: Telefone em formato E.164
    - display_name: Nome do usuário

    Campos de negócio:
    - collected_fields: Dados coletados durante conversa
    - lead_score: Pontuação calculada
    - qualification_level: Nível de qualificação
    """

    user_key: str
    phone_e164: str
    display_name: str | None = None
    city: str | None = None
    is_business: bool = False
    business_name: str | None = None
    role: str | None = None
    collected_fields: dict = Field(default_factory=dict)
    lead_score: int = 0
    qualification_level: QualificationLevel = QualificationLevel.COLD
    created_at: datetime
    updated_at: datetime
    last_interaction: datetime | None = None
    metadata: dict = Field(default_factory=dict)


@dataclass(frozen=True)
class ProfileUpdateEvent:
    """Evento de atualização de perfil para histórico."""

    timestamp: datetime
    field_changed: str
    old_value: str | None  # Mascarado para PII
    new_value: str | None  # Mascarado para PII
    actor: str  # "system" ou ID do agente


class UserProfileStore(Protocol):
    """Porta para persistência de perfis.

    Contrato expandido com:
    - Busca por phone (dedup)
    - Histórico de atualizações
    - LGPD: forget (direito ao esquecimento)
    """

    def get_profile(self, user_key: str) -> UserProfile | None:
        """Retorna perfil se existir."""
        ...

    def get_by_phone(self, phone_e164: str) -> UserProfile | None:
        """Busca perfil por telefone (dedup de contatos)."""
        ...

    def upsert_profile(self, profile: UserProfile) -> None:
        """Atualiza ou cria perfil (controle de PII)."""
        ...

    def update_field(
        self,
        user_key: str,
        field: str,
        value: str | None,
        actor: str = "system",
    ) -> bool:
        """Atualiza campo específico e registra histórico.

        Args:
            user_key: Chave do usuário
            field: Nome do campo
            value: Novo valor
            actor: Quem fez a alteração

        Returns:
            True se atualizado, False se usuário não existe
        """
        ...

    def get_update_history(
        self,
        user_key: str,
        limit: int = 50,
    ) -> list[ProfileUpdateEvent]:
        """Retorna histórico de atualizações do perfil."""
        ...

    def forget(self, user_key: str) -> bool:
        """Remove perfil e histórico (LGPD - direito ao esquecimento).

        Args:
            user_key: Chave do usuário

        Returns:
            True se removido, False se não existia
        """
        ...
