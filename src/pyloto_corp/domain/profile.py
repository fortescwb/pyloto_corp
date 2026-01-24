"""Modelo de perfil do usuário (dados coletados controlados)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel


class UserProfile(BaseModel):
    """Perfil do usuário com PII restrita."""

    user_key: str
    phone_e164: str
    display_name: str | None = None
    collected_fields: dict
    created_at: datetime
    updated_at: datetime


class UserProfileStore(Protocol):
    """Porta para persistência de perfis."""

    def get_profile(self, user_key: str) -> UserProfile | None:
        """Retorna perfil se existir."""

    def upsert_profile(self, profile: UserProfile) -> None:
        """Atualiza ou cria perfil (controle de PII)."""
