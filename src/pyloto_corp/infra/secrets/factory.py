from __future__ import annotations

import logging

from pyloto_corp.observability.logging import get_logger

from .env_provider import EnvSecretProvider
from .gcp_provider import SecretManagerProvider
from .protocol import SecretProvider

logger: logging.Logger = get_logger(__name__)


def create_secret_provider(backend: str = "env", project_id: str | None = None) -> SecretProvider:
    """Factory para criar o provider de secrets apropriado."""
    if backend == "env":
        logger.info("Usando EnvSecretProvider para secrets")
        return EnvSecretProvider()

    if backend == "secret_manager":
        logger.info(
            "Usando SecretManagerProvider para secrets",
            extra={"project_id": project_id},
        )
        return SecretManagerProvider(project_id=project_id)

    raise ValueError(f"Backend de secrets não reconhecido: {backend}")


def get_pepper_secret(provider: SecretProvider | None = None) -> str:
    """Retorna o PEPPER_SECRET usado para derivar user_key."""
    provider = provider or EnvSecretProvider()
    return provider.get_secret("PEPPER_SECRET")


def get_whatsapp_secrets(provider: SecretProvider) -> dict[str, str]:
    """Carrega todos os secrets relacionados ao WhatsApp."""
    secrets: dict[str, str] = {}
    required = ["WHATSAPP_ACCESS_TOKEN"]
    optional = ["WHATSAPP_WEBHOOK_SECRET", "WHATSAPP_VERIFY_TOKEN"]

    for name in required:
        secrets[name.lower()] = provider.get_secret(name)

    for name in optional:
        try:
            secrets[name.lower()] = provider.get_secret(name)
        except RuntimeError:
            logger.warning(
                "Secret opcional não encontrado",
                extra={"secret_name": name},
            )
            secrets[name.lower()] = ""

    return secrets
