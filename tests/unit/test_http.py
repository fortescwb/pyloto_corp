"""Testes unitários para infra/http.py.

Valida cliente HTTP com retry, timeout e logging.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from pyloto_corp.config.settings import Settings
from pyloto_corp.infra.http import (
    HttpClient,
    HttpClientConfig,
    HttpError,
    _calculate_backoff,
    _is_retryable_status,
    _sanitize_url,
    create_http_client,
)


class TestHttpClientConfig:
    """Testes para HttpClientConfig."""

    def test_default_values(self) -> None:
        """Valores padrão devem ser seguros."""
        config = HttpClientConfig()
        assert config.timeout_seconds == 30.0
        assert config.max_retries == 3
        assert config.backoff_base_seconds == 2.0
        assert config.verify_ssl is True
        assert config.circuit_breaker_enabled is False
        assert config.circuit_breaker_fail_max == 5
        assert config.circuit_breaker_reset_timeout_seconds == 60.0
        assert config.circuit_breaker_half_open_max_calls == 1

    def test_custom_values(self) -> None:
        """Deve aceitar valores customizados."""
        config = HttpClientConfig(
            timeout_seconds=10.0,
            max_retries=5,
            backoff_base_seconds=1.0,
            circuit_breaker_enabled=True,
            circuit_breaker_fail_max=2,
            circuit_breaker_reset_timeout_seconds=5.0,
            circuit_breaker_half_open_max_calls=2,
        )
        assert config.timeout_seconds == 10.0
        assert config.max_retries == 5
        assert config.circuit_breaker_enabled is True
        assert config.circuit_breaker_fail_max == 2
        assert config.circuit_breaker_reset_timeout_seconds == 5.0
        assert config.circuit_breaker_half_open_max_calls == 2


class TestHttpError:
    """Testes para HttpError."""

    def test_error_with_status_code(self) -> None:
        """Deve armazenar status code."""
        error = HttpError("Not found", status_code=404)
        assert error.status_code == 404
        assert str(error) == "Not found"

    def test_error_retryable_flag(self) -> None:
        """Deve armazenar flag de retryable."""
        error = HttpError("Server error", status_code=500, is_retryable=True)
        assert error.is_retryable is True


class TestHttpClient:
    """Testes para HttpClient e helpers de módulo."""

    @pytest.fixture
    def client(self) -> HttpClient:
        """Fixture para cliente com config padrão."""
        return HttpClient(HttpClientConfig(max_retries=2))

    def test_sanitize_url_removes_token(self) -> None:
        """Deve remover access_token da URL."""
        url = "https://api.example.com?access_token=secret123&other=value"
        sanitized = _sanitize_url(url)
        assert "secret123" not in sanitized
        assert "access_token=***" in sanitized
        assert "other=value" in sanitized

    def test_sanitize_url_preserves_clean_url(self) -> None:
        """Deve preservar URL sem tokens."""
        url = "https://api.example.com/path"
        assert _sanitize_url(url) == url

    def test_is_retryable_status_429(self) -> None:
        """429 (rate limit) deve ser retryable."""
        assert _is_retryable_status(429) is True

    def test_is_retryable_status_5xx(self) -> None:
        """5xx deve ser retryable."""
        assert _is_retryable_status(500) is True
        assert _is_retryable_status(502) is True
        assert _is_retryable_status(503) is True

    def test_is_retryable_status_4xx(self) -> None:
        """4xx (exceto 429) não deve ser retryable."""
        assert _is_retryable_status(400) is False
        assert _is_retryable_status(401) is False
        assert _is_retryable_status(404) is False

    def test_calculate_backoff(self) -> None:
        """Backoff deve ser exponencial."""
        # attempt 0: 2^0 * 2 = 2
        assert _calculate_backoff(0, 2.0, 30.0) == 2.0
        # attempt 1: 2^1 * 2 = 4
        assert _calculate_backoff(1, 2.0, 30.0) == 4.0
        # attempt 2: 2^2 * 2 = 8
        assert _calculate_backoff(2, 2.0, 30.0) == 8.0

    def test_calculate_backoff_respects_max(self) -> None:
        """Backoff deve respeitar máximo configurado."""
        # attempt 5: 2^5 * 2 = 64, mas max é 10
        assert _calculate_backoff(5, 2.0, 10.0) == 10.0


class TestHttpClientAsync:
    """Testes assíncronos para HttpClient."""

    @pytest.fixture
    def mock_response(self) -> MagicMock:
        """Fixture para response mockado."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.is_success = True
        return response

    @pytest.mark.asyncio
    async def test_get_success(self, mock_response: MagicMock) -> None:
        """GET deve retornar response em sucesso."""
        client = HttpClient()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request.return_value = mock_response
        mock_httpx_client.is_closed = False
        client._client = mock_httpx_client

        response = await client.get("https://api.example.com")

        assert response.status_code == 200
        mock_httpx_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_with_json(self, mock_response: MagicMock) -> None:
        """POST deve enviar JSON."""
        client = HttpClient()

        mock_httpx_client = AsyncMock()
        mock_httpx_client.request.return_value = mock_response
        mock_httpx_client.is_closed = False
        client._client = mock_httpx_client

        payload = {"key": "value"}
        await client.post("https://api.example.com", json=payload)

        mock_httpx_client.request.assert_called_once_with(
            "POST",
            "https://api.example.com",
            json=payload,
        )

    @pytest.mark.asyncio
    async def test_retry_on_5xx(self) -> None:
        """Deve fazer retry em erros 5xx."""
        config = HttpClientConfig(max_retries=2)
        client = HttpClient(config)

        # Primeira e segunda chamadas: 500
        # Terceira chamada: 200
        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 500
        error_response.is_success = False

        success_response = MagicMock(spec=httpx.Response)
        success_response.status_code = 200
        success_response.is_success = True

        mock_httpx_client = AsyncMock()
        mock_httpx_client.is_closed = False
        mock_httpx_client.request.side_effect = [
            error_response,
            error_response,
            success_response,
        ]
        client._client = mock_httpx_client

        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await client.get("https://api.example.com")

        assert response.status_code == 200
        assert mock_httpx_client.request.call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(self) -> None:
        """Não deve fazer retry em erros 4xx."""
        config = HttpClientConfig(max_retries=3)
        client = HttpClient(config)

        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 400
        error_response.is_success = False

        mock_httpx_client = AsyncMock()
        mock_httpx_client.is_closed = False
        mock_httpx_client.request.return_value = error_response
        client._client = mock_httpx_client

        with pytest.raises(HttpError) as exc_info:
            await client.get("https://api.example.com")

        assert exc_info.value.status_code == 400
        assert exc_info.value.is_retryable is False
        # Só uma chamada, sem retry
        assert mock_httpx_client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_exhaust_retries(self) -> None:
        """Deve levantar erro após esgotar retries."""
        config = HttpClientConfig(max_retries=2)
        client = HttpClient(config)

        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 503
        error_response.is_success = False

        mock_httpx_client = AsyncMock()
        mock_httpx_client.is_closed = False
        mock_httpx_client.request.return_value = error_response
        client._client = mock_httpx_client

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(HttpError) as exc_info,
        ):
            await client.get("https://api.example.com")

        assert exc_info.value.status_code == 503
        # 1 tentativa inicial + 2 retries = 3 chamadas
        assert mock_httpx_client.request.call_count == 3

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Deve funcionar como async context manager."""
        async with HttpClient() as client:
            assert client is not None

    @pytest.mark.asyncio
    async def test_close_client(self) -> None:
        """close() deve fechar o cliente httpx."""
        client = HttpClient()
        mock_httpx_client = AsyncMock()
        mock_httpx_client.is_closed = False
        client._client = mock_httpx_client

        await client.close()

        mock_httpx_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_and_fast_fails(self) -> None:
        """Breaker deve abrir após falha retryable e falhar rápido depois."""

        config = HttpClientConfig(
            max_retries=0,
            circuit_breaker_enabled=True,
            circuit_breaker_fail_max=1,
            circuit_breaker_reset_timeout_seconds=60.0,
        )
        client = HttpClient(config)
        assert client._circuit_breaker is not None
        client._circuit_breaker._clock = lambda: 0.0

        client._request_with_retry = AsyncMock(
            side_effect=HttpError("falha", is_retryable=True)
        )

        with pytest.raises(HttpError):
            await client.get("https://api.example.com")

        with pytest.raises(HttpError) as exc_info:
            await client.get("https://api.example.com")

        assert exc_info.value.is_retryable is False
        assert client._request_with_retry.call_count == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_recovers_after_reset_timeout(self) -> None:
        """Breaker deve permitir half-open após timeout e fechar em sucesso."""

        config = HttpClientConfig(
            max_retries=0,
            circuit_breaker_enabled=True,
            circuit_breaker_fail_max=1,
            circuit_breaker_reset_timeout_seconds=1.0,
            circuit_breaker_half_open_max_calls=1,
        )
        client = HttpClient(config)
        breaker = client._circuit_breaker
        assert breaker is not None

        current_time = 0.0
        breaker._clock = lambda: current_time
        client._request_with_retry = AsyncMock(
            side_effect=HttpError("falha", is_retryable=True)
        )

        with pytest.raises(HttpError):
            await client.get("https://api.example.com")

        current_time = 2.0
        success_response = MagicMock(spec=httpx.Response)
        success_response.is_success = True
        success_response.status_code = 200
        client._request_with_retry = AsyncMock(return_value=success_response)

        response = await client.get("https://api.example.com")

        assert response is success_response
        assert breaker.state == "closed"
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_reopens_on_half_open_failure(self) -> None:
        """Falha em half-open deve reabrir e bloquear novas chamadas."""

        config = HttpClientConfig(
            max_retries=0,
            circuit_breaker_enabled=True,
            circuit_breaker_fail_max=1,
            circuit_breaker_reset_timeout_seconds=0.5,
            circuit_breaker_half_open_max_calls=1,
        )
        client = HttpClient(config)
        breaker = client._circuit_breaker
        assert breaker is not None

        current_time = 0.0
        breaker._clock = lambda: current_time
        client._request_with_retry = AsyncMock(
            side_effect=HttpError("falha", is_retryable=True)
        )

        with pytest.raises(HttpError):
            await client.get("https://api.example.com")

        current_time = 1.0
        client._request_with_retry = AsyncMock(
            side_effect=HttpError("falha", is_retryable=True)
        )

        with pytest.raises(HttpError):
            await client.get("https://api.example.com")

        with pytest.raises(HttpError):
            await client.get("https://api.example.com")

        assert breaker.state == "open"
        assert client._request_with_retry.call_count == 1


class TestCreateHttpClient:
    """Testes para factory function create_http_client."""

    def test_creates_client_with_settings(self) -> None:
        """Deve criar cliente com configurações de Settings."""
        settings = Settings(
            whatsapp_request_timeout_seconds=60,
            whatsapp_max_retries=5,
            whatsapp_retry_backoff_seconds=3,
        )

        client = create_http_client(settings)

        assert client._config.timeout_seconds == 60.0
        assert client._config.max_retries == 5
        assert client._config.backoff_base_seconds == 3.0

    def test_includes_user_agent(self) -> None:
        """Deve incluir User-Agent com service_name/version."""
        settings = Settings(service_name="test_service", version="1.2.3")

        client = create_http_client(settings)

        assert "User-Agent" in client._config.default_headers
        assert "test_service/1.2.3" in client._config.default_headers["User-Agent"]

    def test_verify_ssl_in_production(self) -> None:
        """SSL deve ser verificado em produção."""
        settings = Settings(environment="production")

        client = create_http_client(settings)

        assert client._config.verify_ssl is True

    def test_verify_ssl_disabled_in_dev(self) -> None:
        """SSL pode ser desabilitado em desenvolvimento."""
        settings = Settings(environment="development")

        client = create_http_client(settings)

        assert client._config.verify_ssl is False

    def test_circuit_breaker_config_from_settings(self) -> None:
        """Circuit breaker deve refletir configurações fornecidas."""

        settings = Settings(
            whatsapp_circuit_breaker_enabled=True,
            whatsapp_circuit_breaker_fail_max=2,
            whatsapp_circuit_breaker_reset_timeout_seconds=5.0,
            whatsapp_circuit_breaker_half_open_max_calls=3,
        )

        client = create_http_client(settings)

        assert client._config.circuit_breaker_enabled is True
        assert client._config.circuit_breaker_fail_max == 2
        assert client._config.circuit_breaker_reset_timeout_seconds == 5.0
        assert client._config.circuit_breaker_half_open_max_calls == 3
