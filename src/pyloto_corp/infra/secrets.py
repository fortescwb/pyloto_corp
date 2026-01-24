"""Acesso a segredos via Secret Manager e providers locais.

Este módulo implementa o padrão de porta/adaptador para leitura de segredos,
permitindo diferentes backends (env vars, Secret Manager, etc.).

Conforme regras_e_padroes.md:
- Nunca logar valores de secrets
- Usar fail-closed em caso de erro
- Secrets em produção devem vir do Secret Manager
"""

from __future__ import annotations

import logging
import os
from typing import Protocol

from pyloto_corp.observability.logging import get_logger

logger: logging.Logger = get_logger(__name__)


class SecretProvider(Protocol):
    """Porta para leitura de segredos.

    Implementações devem:
    - Nunca logar o valor do secret
    - Levantar RuntimeError se secret não encontrado
    - Suportar versionamento quando aplicável
    """

    def get_secret(self, name: str, version: str = "latest") -> str:
        """Obtém o valor do segredo.

        Args:
            name: Nome do secret (ex: WHATSAPP_ACCESS_TOKEN)
            version: Versão do secret (default: latest)

        Returns:
            Valor do secret como string

        Raises:
            RuntimeError: Se secret não encontrado ou inacessível
        """
        ...

    def secret_exists(self, name: str) -> bool:
        """Verifica se um secret existe sem retornar seu valor."""
        ...


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


class SecretManagerProvider:
    """Provider para Google Cloud Secret Manager.

    Requer google-cloud-secret-manager instalado e
    Application Default Credentials configurado.

    Uso em produção:
    - Secrets armazenados no Secret Manager do projeto GCP
    - Acesso via service account com permissão secretAccessor
    - Versionamento automático habilitado
    """

    def __init__(self, project_id: str | None = None) -> None:
        """Inicializa o provider.

        Args:
            project_id: ID do projeto GCP. Se None, usa GOOGLE_CLOUD_PROJECT.
        """
        self._project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self._client = None  # Lazy loading

    def _get_client(self):
        """Retorna cliente do Secret Manager (lazy loading).

        TODO: Implementar quando google-cloud-secret-manager for adicionado
        às dependências de produção.
        """
        if self._client is None:
            try:
                # pylint: disable=import-outside-toplevel
                from google.cloud import secretmanager

                self._client = secretmanager.SecretManagerServiceClient()
            except ImportError as e:
                logger.error(
                    "google-cloud-secret-manager não instalado",
                    extra={"error": str(e)},
                )
                raise RuntimeError(
                    "Dependência google-cloud-secret-manager não encontrada. "
                    "Instale com: pip install google-cloud-secret-manager"
                ) from e
        return self._client

    def _build_secret_name(self, name: str, version: str = "latest") -> str:
        """Constrói o nome completo do secret no formato GCP."""
        if not self._project_id:
            raise RuntimeError(
                "project_id não configurado. "
                "Defina GOOGLE_CLOUD_PROJECT ou passe project_id ao construtor."
            )
        return f"projects/{self._project_id}/secrets/{name}/versions/{version}"

    def get_secret(self, name: str, version: str = "latest") -> str:
        """Lê secret do Secret Manager.

        Args:
            name: Nome do secret no Secret Manager
            version: Versão específica ou "latest"

        Returns:
            Valor do secret como string

        Raises:
            RuntimeError: Se secret não encontrado ou erro de acesso
        """
        client = self._get_client()
        secret_path = self._build_secret_name(name, version)

        try:
            response = client.access_secret_version(name=secret_path)
            payload = response.payload.data.decode("utf-8")

            logger.info(
                "Secret lido do Secret Manager",
                extra={
                    "secret_name": name,
                    "version": version,
                    "provider": "secret_manager",
                },
            )
            return payload

        except Exception as e:
            # Não expor detalhes do erro em logs (pode conter info sensível)
            logger.error(
                "Falha ao acessar Secret Manager",
                extra={
                    "secret_name": name,
                    "version": version,
                    "error_type": type(e).__name__,
                },
            )
            raise RuntimeError(
                f"Não foi possível acessar secret {name}: acesso negado ou não existe"
            ) from e

    def secret_exists(self, name: str) -> bool:
        """Verifica se um secret existe no Secret Manager."""
        client = self._get_client()

        try:
            secret_path = f"projects/{self._project_id}/secrets/{name}"
            client.get_secret(name=secret_path)
            return True
        except Exception:
            return False


def create_secret_provider(
    backend: str = "env",
    project_id: str | None = None,
) -> SecretProvider:
    """Factory para criar o provider de secrets apropriado.

    Args:
        backend: "env" para variáveis de ambiente, "secret_manager" para GCP
        project_id: ID do projeto GCP (apenas para secret_manager)

    Returns:
        Instância do provider configurado

    Raises:
        ValueError: Se backend não reconhecido
    """
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
    """Retorna o PEPPER_SECRET usado para derivar user_key.

    O PEPPER_SECRET é um valor fixo usado para HMAC de identificadores
    de usuário, garantindo que o mesmo phone gere o mesmo user_key
    sem expor o phone original.

    Em dev: usa env var.
    Em produção: usar Secret Manager.
    """
    provider = provider or EnvSecretProvider()
    return provider.get_secret("PEPPER_SECRET")


def get_whatsapp_secrets(provider: SecretProvider) -> dict[str, str]:
    """Carrega todos os secrets relacionados ao WhatsApp.

    Retorna dicionário com:
    - access_token
    - webhook_secret
    - verify_token

    Útil para inicialização do serviço.

    Raises:
        RuntimeError: Se algum secret obrigatório não for encontrado
    """
    secrets = {}
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
