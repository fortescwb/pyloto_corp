"""Implementação de SecretProvider — Integração com Secrets Manager.

Responsabilidades:
- Implementar SecretProvider usando get_pepper_secret() existente
- Manter compatibilidade com código existente
- Permitir injeção em Application

Conforme regras_e_padroes.md (implementação isolada).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyloto_corp.domain.secret_provider import SecretProvider
from pyloto_corp.infra.secrets import get_pepper_secret

if TYPE_CHECKING:
    pass


class InfraSecretProvider(SecretProvider):
    """Implementação que delega para infra.secrets."""

    def get_pepper_secret(self) -> str:
        """Retorna pepper_secret usando get_pepper_secret() existente."""
        return get_pepper_secret()
