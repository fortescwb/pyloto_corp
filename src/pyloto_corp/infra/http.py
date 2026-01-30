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
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx

from pyloto_corp.infra.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.config.settings import Settings

logger: logging.Logger = get_logger(__name__)

# Regex pré-compilado para sanitização de URL
_ACCESS_TOKEN_PATTERN = re.compile(r"access_token=[^&]+")


def _sanitize_url(url: str) -> str:
    """Remove tokens e credenciais da URL para logging seguro."""
    if "access_token=" in url:
        return _ACCESS_TOKEN_PATTERN.sub("access_token=***", url)
    return url


@dataclass
class HttpClientConfig:
    """Configuração do cliente HTTP.

    Valores padrão são seguros e conservadores.
    """

    timeout_seconds: float = 30.0
    max_retries: int = 3
    backoff_base_seconds: float = 2.0
    backoff_max_seconds: float = 30.0
    default_headers: dict[str, str] = field(default_factory=dict)
    verify_ssl: bool = True
    circuit_breaker_enabled: bool = False
    circuit_breaker_fail_max: int = 5
    circuit_breaker_reset_timeout_seconds: float = 60.0
    circuit_breaker_half_open_max_calls: int = 1


class HttpError(Exception):
    """Erro de requisição HTTP sem expor informações sensíveis."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        is_retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.is_retryable = is_retryable


def _is_retryable_status(status_code: int) -> bool:
    """Determina se status HTTP permite retry (429 ou 5xx)."""
    return status_code == 429 or 500 <= status_code < 600


def _calculate_backoff(
    attempt: int,
    base_seconds: float,
    max_seconds: float,
) -> float:
    """Calcula tempo de espera com backoff exponencial."""
    backoff = (2**attempt) * base_seconds
    return min(backoff, max_seconds)


def _log_request_start(method: str, url: str, attempt: int, max_r: int) -> None:
    """Loga início de requisição sem dados sensíveis."""
    logger.debug(
        "Executando requisição HTTP",
        extra={
            "method": method,
            "url": _sanitize_url(url),
            "attempt": attempt + 1,
            "max_retries": max_r,
        },
    )


def _log_request_success(method: str, url: str, status_code: int) -> None:
    """Loga sucesso de requisição."""
    logger.debug(
        "Requisição HTTP bem-sucedida",
        extra={
            "method": method,
            "url": _sanitize_url(url),
            "status_code": status_code,
        },
    )


def _log_non_retryable_error(method: str, url: str, status_code: int) -> None:
    """Loga erro não retentável."""
    logger.warning(
        "Requisição HTTP falhou (não retryable)",
        extra={
            "method": method,
            "url": _sanitize_url(url),
            "status_code": status_code,
        },
    )


def _log_transient_error(
    msg: str,
    method: str,
    url: str,
    attempt: int,
    error: str,
) -> None:
    """Loga erro transitório (timeout, conexão)."""
    logger.warning(
        msg,
        extra={
            "method": method,
            "url": _sanitize_url(url),
            "attempt": attempt + 1,
            "error": error,
        },
    )


def _log_unexpected_error(method: str, url: str, error_type: str) -> None:
    """Loga erro inesperado."""
    logger.error(
        "Erro inesperado em requisição HTTP",
        extra={
            "method": method,
            "url": _sanitize_url(url),
            "error_type": error_type,
        },
    )


def _log_backoff(backoff: float, next_attempt: int) -> None:
    """Loga aguardo de backoff."""
    logger.info(
        "Aguardando backoff antes de retry",
        extra={"backoff_seconds": backoff, "next_attempt": next_attempt},
    )


def _log_retries_exhausted(method: str, url: str, total: int) -> None:
    """Loga esgotamento de retries."""
    logger.error(
        "Esgotou tentativas de retry",
        extra={
            "method": method,
            "url": _sanitize_url(url),
            "total_attempts": total,
        },
    )


def _handle_transient_exception(
    exc: Exception,
    method: str,
    url: str,
    attempt: int,
) -> HttpError:
    """Trata exceções transitórias (timeout, conexão) e retorna HttpError."""
    if isinstance(exc, httpx.TimeoutException):
        _log_transient_error("Timeout em requisição HTTP", method, url, attempt, str(exc))
        return HttpError("Timeout", is_retryable=True)

    if isinstance(exc, httpx.ConnectError):
        _log_transient_error("Erro de conexão HTTP", method, url, attempt, str(exc))
        return HttpError("Erro de conexão", is_retryable=True)

    _log_unexpected_error(method, url, type(exc).__name__)
    raise HttpError(f"Erro inesperado: {type(exc).__name__}") from exc


class HttpClient:
    """Cliente HTTP assíncrono com retry e logging.

    Uso típico:
        async with HttpClient(config) as client:
            response = await client.post(url, json=payload)
    """

    def __init__(self, config: HttpClientConfig | None = None) -> None:
        """Inicializa cliente com configuração."""
        self._config = config or HttpClientConfig()
        self._client: httpx.AsyncClient | None = None
        self._circuit_breaker: CircuitBreaker | None = None
        if self._config.circuit_breaker_enabled:
            breaker_cfg = CircuitBreakerConfig(
                enabled=self._config.circuit_breaker_enabled,
                fail_max=self._config.circuit_breaker_fail_max,
                reset_timeout_seconds=self._config.circuit_breaker_reset_timeout_seconds,
                half_open_max_calls=self._config.circuit_breaker_half_open_max_calls,
            )
            self._circuit_breaker = CircuitBreaker(breaker_cfg)

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
        last_error: HttpError | None = None
        cfg = self._config

        for attempt in range(cfg.max_retries + 1):
            _log_request_start(method, url, attempt, cfg.max_retries)

            try:
                response = await client.request(method, url, **kwargs)
                result = self._process_response(response, method, url)
                if result is not None:
                    return result
                last_error = HttpError(
                    f"HTTP {response.status_code}",
                    status_code=response.status_code,
                    is_retryable=True,
                )

            except HttpError:
                raise
            except Exception as exc:
                last_error = _handle_transient_exception(exc, method, url, attempt)

            await self._wait_backoff_if_needed(attempt)

        _log_retries_exhausted(method, url, cfg.max_retries + 1)
        raise last_error or HttpError("Falha após todos os retries")

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Orquestra requisição com circuit breaker e retry."""

        breaker = self._circuit_breaker
        if breaker:
            allowed = await breaker.allow_request()
            if not allowed:
                logger.warning(
                    "Circuit breaker aberto - falha rápida",
                    extra={
                        "method": method,
                        "url": _sanitize_url(url),
                        "breaker_state": breaker.state,
                    },
                )
                raise HttpError("Circuit breaker aberto", is_retryable=False)

        try:
            response = await self._request_with_retry(method, url, **kwargs)
        except HttpError as exc:
            if breaker:
                state = await breaker.record_failure(exc.is_retryable)
                if state == "open":
                    logger.error(
                        "Circuit breaker aberto após falhas consecutivas",
                        extra={
                            "method": method,
                            "url": _sanitize_url(url),
                            "breaker_failures": breaker.failure_count,
                        },
                    )
            raise

        if breaker:
            previous_state = breaker.state
            await breaker.record_success()
            if previous_state != "closed":
                logger.info(
                    "Circuit breaker fechado após sucesso",
                    extra={
                        "method": method,
                        "url": _sanitize_url(url),
                    },
                )

        return response

    def _process_response(
        self,
        response: httpx.Response,
        method: str,
        url: str,
    ) -> httpx.Response | None:
        """Processa resposta: retorna se sucesso, levanta se não retentável.

        Returns:
            Response se sucesso, None se retentável
        """
        if response.is_success:
            _log_request_success(method, url, response.status_code)
            return response

        if not _is_retryable_status(response.status_code):
            _log_non_retryable_error(method, url, response.status_code)
            raise HttpError(
                f"HTTP {response.status_code}",
                status_code=response.status_code,
                is_retryable=False,
            )
        return None

    async def _wait_backoff_if_needed(self, attempt: int) -> None:
        """Aguarda backoff se ainda há retries disponíveis."""
        cfg = self._config
        if attempt < cfg.max_retries:
            backoff = _calculate_backoff(
                attempt,
                cfg.backoff_base_seconds,
                cfg.backoff_max_seconds,
            )
            _log_backoff(backoff, attempt + 2)
            await asyncio.sleep(backoff)

    # Métodos de conveniência

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Executa GET com retry."""
        return await self._request("GET", url, **kwargs)

    async def post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executa POST com retry."""
        return await self._request("POST", url, json=json, **kwargs)

    async def put(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executa PUT com retry."""
        return await self._request("PUT", url, json=json, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        """Executa DELETE com retry."""
        return await self._request("DELETE", url, **kwargs)


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
        circuit_breaker_enabled=settings.whatsapp_circuit_breaker_enabled,
        circuit_breaker_fail_max=settings.whatsapp_circuit_breaker_fail_max,
        circuit_breaker_reset_timeout_seconds=float(
            settings.whatsapp_circuit_breaker_reset_timeout_seconds
        ),
        circuit_breaker_half_open_max_calls=settings.whatsapp_circuit_breaker_half_open_max_calls,
    )

    logger.info(
        "Cliente HTTP criado",
        extra={
            "timeout_seconds": config.timeout_seconds,
            "max_retries": config.max_retries,
        },
    )

    return HttpClient(config)
