"""Cliente HTTP centralizado com retry, timeout e logging.

Este módulo fornece um cliente HTTP configurável para chamadas
externas (principalmente Meta API), com:
- Retry com backoff exponencial
- Timeouts configuráveis
- Logging estruturado (sem PII)
- Injeção de headers padrão

Conforme regras_e_padroes.md:
- Nunca logar payloads com PII
- Sempre usar timeout
- Retry com backoff para resiliência
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx

from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.config.settings import Settings

logger: logging.Logger = get_logger(__name__)


@dataclass
class HttpClientConfig:
    """Configuração do cliente HTTP.

    Valores padrão são seguros e conservadores.
    """

    timeout_seconds: float = 30.0
    max_retries: int = 3
    backoff_base_seconds: float = 2.0
    backoff_max_seconds: float = 30.0
    # Headers padrão injetados em todas as requisições
    default_headers: dict[str, str] = field(default_factory=dict)
    # Se True, verifica SSL (sempre True em produção)
    verify_ssl: bool = True


class HttpError(Exception):
    """Erro de requisição HTTP.

    Encapsula detalhes do erro sem expor informações sensíveis.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        is_retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.is_retryable = is_retryable


class HttpClient:
    """Cliente HTTP assíncrono com retry e logging.

    Uso típico:
        async with HttpClient(config) as client:
            response = await client.post(url, json=payload)

    Ou sem context manager:
        client = HttpClient(config)
        response = await client.get(url)
        await client.close()
    """

    def __init__(self, config: HttpClientConfig | None = None) -> None:
        """Inicializa cliente com configuração.

        Args:
            config: Configuração do cliente. Usa padrões se None.
        """
        self._config = config or HttpClientConfig()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Retorna cliente httpx (lazy loading)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._config.timeout_seconds),
                headers=self._config.default_headers,
                verify=self._config.verify_ssl,
            )
        return self._client

    async def close(self) -> None:
        """Fecha o cliente e libera recursos."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> HttpClient:
        """Suporte a async context manager."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Fecha cliente ao sair do context."""
        await self.close()

    def _is_retryable_status(self, status_code: int) -> bool:
        """Determina se status HTTP permite retry.

        Retryable: 429 (rate limit), 5xx (server errors)
        Não retryable: 4xx (client errors, exceto 429)
        """
        # Rate limit ou server errors são retryable
        return status_code == 429 or 500 <= status_code < 600

    def _calculate_backoff(self, attempt: int) -> float:
        """Calcula tempo de espera com backoff exponencial."""
        # 2^attempt * base, limitado ao máximo
        backoff = (2**attempt) * self._config.backoff_base_seconds
        return min(backoff, self._config.backoff_max_seconds)

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executa requisição com retry automático.

        Args:
            method: Método HTTP (GET, POST, etc.)
            url: URL da requisição
            **kwargs: Argumentos passados para httpx

        Returns:
            Resposta HTTP

        Raises:
            HttpError: Se todas as tentativas falharem
        """
        client = await self._get_client()
        last_error: Exception | None = None

        for attempt in range(self._config.max_retries + 1):
            try:
                logger.debug(
                    "Executando requisição HTTP",
                    extra={
                        "method": method,
                        "url": self._sanitize_url(url),
                        "attempt": attempt + 1,
                        "max_retries": self._config.max_retries,
                    },
                )

                response = await client.request(method, url, **kwargs)

                # Sucesso
                if response.is_success:
                    logger.debug(
                        "Requisição HTTP bem-sucedida",
                        extra={
                            "method": method,
                            "url": self._sanitize_url(url),
                            "status_code": response.status_code,
                        },
                    )
                    return response

                # Erro não retryable
                if not self._is_retryable_status(response.status_code):
                    logger.warning(
                        "Requisição HTTP falhou (não retryable)",
                        extra={
                            "method": method,
                            "url": self._sanitize_url(url),
                            "status_code": response.status_code,
                        },
                    )
                    raise HttpError(
                        f"HTTP {response.status_code}",
                        status_code=response.status_code,
                        is_retryable=False,
                    )

                # Erro retryable - continua loop
                last_error = HttpError(
                    f"HTTP {response.status_code}",
                    status_code=response.status_code,
                    is_retryable=True,
                )

            except httpx.TimeoutException as e:
                last_error = HttpError("Timeout", is_retryable=True)
                logger.warning(
                    "Timeout em requisição HTTP",
                    extra={
                        "method": method,
                        "url": self._sanitize_url(url),
                        "attempt": attempt + 1,
                        "error": str(e),
                    },
                )

            except httpx.ConnectError as e:
                last_error = HttpError("Erro de conexão", is_retryable=True)
                logger.warning(
                    "Erro de conexão HTTP",
                    extra={
                        "method": method,
                        "url": self._sanitize_url(url),
                        "attempt": attempt + 1,
                        "error": str(e),
                    },
                )

            except HttpError:
                raise

            except Exception as e:
                last_error = HttpError(f"Erro inesperado: {type(e).__name__}")
                logger.error(
                    "Erro inesperado em requisição HTTP",
                    extra={
                        "method": method,
                        "url": self._sanitize_url(url),
                        "error_type": type(e).__name__,
                    },
                )
                raise

            # Aguarda backoff antes do próximo retry
            if attempt < self._config.max_retries:
                backoff = self._calculate_backoff(attempt)
                logger.info(
                    "Aguardando backoff antes de retry",
                    extra={
                        "backoff_seconds": backoff,
                        "next_attempt": attempt + 2,
                    },
                )
                await asyncio.sleep(backoff)

        # Esgotou retries
        logger.error(
            "Esgotou tentativas de retry",
            extra={
                "method": method,
                "url": self._sanitize_url(url),
                "total_attempts": self._config.max_retries + 1,
            },
        )
        raise last_error or HttpError("Falha após todos os retries")

    def _sanitize_url(self, url: str) -> str:
        """Remove tokens e credenciais da URL para logging."""
        # Remove access_token se presente na URL
        if "access_token=" in url:
            import re

            url = re.sub(r"access_token=[^&]+", "access_token=***", url)
        return url

    # Métodos de conveniência

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Executa GET com retry."""
        return await self._request_with_retry("GET", url, **kwargs)

    async def post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executa POST com retry."""
        return await self._request_with_retry("POST", url, json=json, **kwargs)

    async def put(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executa PUT com retry."""
        return await self._request_with_retry("PUT", url, json=json, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        """Executa DELETE com retry."""
        return await self._request_with_retry("DELETE", url, **kwargs)


def create_http_client(settings: Settings | None = None) -> HttpClient:
    """Factory para criar cliente HTTP configurado.

    Args:
        settings: Configurações da aplicação. Se None, usa get_settings()

    Returns:
        HttpClient configurado conforme settings
    """
    if settings is None:
        from pyloto_corp.config.settings import get_settings

        settings = get_settings()

    config = HttpClientConfig(
        timeout_seconds=float(settings.whatsapp_request_timeout_seconds),
        max_retries=settings.whatsapp_max_retries,
        backoff_base_seconds=float(settings.whatsapp_retry_backoff_seconds),
        default_headers={
            "User-Agent": f"{settings.service_name}/{settings.version}",
        },
        verify_ssl=settings.is_production,
    )

    logger.info(
        "Cliente HTTP criado",
        extra={
            "timeout_seconds": config.timeout_seconds,
            "max_retries": config.max_retries,
        },
    )

    return HttpClient(config)
