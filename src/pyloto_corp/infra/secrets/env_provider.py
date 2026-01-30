from __future__ import annotations

import logging
import os

from pyloto_corp.observability.logging import get_logger

logger: logging.Logger = get_logger(__name__)


class EnvSecretProvider:
    """Provider para desenvolvimento local via variáveis de ambiente.

    Não deve ser usado em produção. Útil para:
    - Desenvolvimento local
    - Testes unitários
    - CI/CD com secrets injetados
    """

    def get_secret(self, name: str, version: str = "latest") -> str:
        """Lê secret de variável de ambiente.

        O parâmetro version é ignorado (env vars não têm versões).
        """
        value = os.getenv(name)
        if not value:
            logger.warning(
                "Secret não encontrado no ambiente",
                extra={"secret_name": name, "provider": "env"},
            )
            raise RuntimeError(f"Secret {name} não encontrado no ambiente")

        logger.debug(
            "Secret lido do ambiente",
            extra={"secret_name": name, "provider": "env"},
        )
        return value

    def secret_exists(self, name: str) -> bool:
        """Verifica se env var existe."""
        return os.getenv(name) is not None
