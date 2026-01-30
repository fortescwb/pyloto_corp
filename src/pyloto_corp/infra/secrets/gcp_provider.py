from __future__ import annotations

import logging
import os

from pyloto_corp.observability.logging import get_logger

logger: logging.Logger = get_logger(__name__)


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
        self._project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self._client = None  # Lazy loading

    def _get_client(self):
        """Retorna cliente do Secret Manager (lazy loading)."""
        if self._client is None:
            try:
                from google.cloud import secretmanager  # type: ignore

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

        except Exception as e:  # pylint: disable=broad-except
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
        client = self._get_client()

        try:
            secret_path = f"projects/{self._project_id}/secrets/{name}"
            client.get_secret(name=secret_path)
            return True
        except Exception:  # pylint: disable=broad-except
            return False
