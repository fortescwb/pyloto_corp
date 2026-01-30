"""Shim de compatibilidade para providers de secrets.

Mantém imports legados apontando para a nova estrutura em infra/secrets/.
"""

from __future__ import annotations

from pyloto_corp.infra.secrets.env_provider import EnvSecretProvider
from pyloto_corp.infra.secrets.factory import (
    create_secret_provider,
    get_pepper_secret,
    get_whatsapp_secrets,
)
from pyloto_corp.infra.secrets.gcp_provider import SecretManagerProvider
from pyloto_corp.infra.secrets.protocol import SecretProvider

__all__ = [
    "SecretProvider",
    "EnvSecretProvider",
    "SecretManagerProvider",
    "create_secret_provider",
    "get_pepper_secret",
    "get_whatsapp_secrets",
]
