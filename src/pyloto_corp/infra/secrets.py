"""Acesso a segredos via Secret Manager (esqueleto)."""

from __future__ import annotations

import os
from typing import Protocol


class SecretProvider(Protocol):
    """Porta para leitura de segredos."""

    def get_secret(self, name: str) -> str:
        """Obtém o valor do segredo."""


class EnvSecretProvider:
    """Provider simples para desenvolvimento local via env var."""

    def get_secret(self, name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise RuntimeError(f"Secret {name} não encontrado no ambiente")
        return value


class SecretManagerProvider:
    """Provider para Google Secret Manager (placeholder)."""

    def get_secret(self, _name: str) -> str:
        raise NotImplementedError("Secret Manager ainda não integrado")


def get_pepper_secret(provider: SecretProvider | None = None) -> str:
    """Retorna o PEPPER_SECRET usado para derivar user_key.

    Em dev: usa env var. Em produção: substituir por Secret Manager.
    """

    provider = provider or EnvSecretProvider()
    return provider.get_secret("PEPPER_SECRET")
