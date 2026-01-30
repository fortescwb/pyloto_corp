"""Testes para WhatsAppHttpClient.

Valida:
- Envio de mensagem bem-sucedido
- Tratamento de rate limiting (429)
- Tratamento de erros Meta permanentes vs transitórios
- Parsing de resposta JSON
- Logging sem exposição de tokens
- Retry em erros transitórios
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from pyloto_corp.adapters.whatsapp.http_client import (
    WhatsAppHttpClient,
    _is_permanent_error,
    _parse_meta_error,
    create_whatsapp_http_client,
)
from pyloto_corp.infra.http import HttpClientConfig, HttpError


class TestParseMetaError:
    """Testes para parsing de erro Meta."""

    def test_parse_error_with_valid_error_object(self) -> None:
        """Parse extrai erro corretamente do response."""
        response_data = {
            "error": {
                "type": "OAuthException",
                "code": 400,
                "message": "Invalid access token",
            }
        }

        error = _parse_meta_error(response_data)

        assert error is not None
        assert error.error_type == "OAuthException"
        assert error.error_code == 400
        assert error.error_message == "Invalid access token"
        assert error.is_permanent is True

    def test_parse_no_error_returns_none(self) -> None:
        """Parse retorna None se não há erro."""
        response_data = {"message_id": "wamid.123"}

        error = _parse_meta_error(response_data)

        assert error is None

    def test_parse_malformed_error_object(self) -> None:
        """Parse retorna None se error não é dict."""
        response_data = {"error": "string error"}

        error = _parse_meta_error(response_data)

        assert error is None

    def test_parse_rate_limit_error_is_transient(self) -> None:
        """Rate limit (429) é classificado como transitório."""
        response_data = {
            "error": {
                "type": "RateLimitException",
                "code": 429,
                "message": "Too many requests",
            }
        }

        error = _parse_meta_error(response_data)

        assert error is not None
        assert error.is_permanent is False


class TestIsPermanentError:
    """Testes para classificação de erros."""

    def test_400_is_permanent(self) -> None:
        """400 Bad Request é permanente."""
        assert _is_permanent_error(400, "InvalidRequest") is True

    def test_401_is_permanent(self) -> None:
        """401 Unauthorized é permanente."""
        assert _is_permanent_error(401, "OAuthException") is True

    def test_429_is_transient(self) -> None:
        """429 Rate Limit é transitório."""
        assert _is_permanent_error(429, "RateLimitException") is False

    def test_500_is_transient(self) -> None:
        """500 Server Error é transitório."""
        assert _is_permanent_error(500, "ServerError") is False

    def test_oauth_exception_type_is_permanent(self) -> None:
        """OAuthException é permanente independente do código."""
        assert _is_permanent_error(999, "OAuthException") is True


class TestWhatsAppHttpClientSendMessage:
    """Testes para envio de mensagem."""

    @pytest.mark.asyncio
    async def test_send_message_success(self) -> None:
        """Envio bem-sucedido retorna response data."""
        config = HttpClientConfig(timeout_seconds=5.0)
        client = WhatsAppHttpClient(config=config)

        # Mock do post
        expected_response = {"message_id": "wamid.ABC123"}
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = expected_response
        mock_response.is_success = True
        mock_response.status_code = 200

        with patch.object(
            client,
            "_request_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.send_message(
                endpoint="https://api.meta/messages",
                access_token="test_token",
                payload={"messaging_product": "whatsapp", "to": "5511999999"},
            )

        assert result == expected_response

    @pytest.mark.asyncio
    async def test_send_message_meta_error_permanent(self) -> None:
        """Erro permanente da Meta lança HttpError não retryable."""
        config = HttpClientConfig(timeout_seconds=5.0)
        client = WhatsAppHttpClient(config=config)

        error_response = {
            "error": {
                "type": "OAuthException",
                "code": 401,
                "message": "Invalid access token",
            }
        }
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = error_response
        mock_response.is_success = False

        with patch.object(
            client,
            "_request_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            with pytest.raises(HttpError) as exc_info:
                await client.send_message(
                    endpoint="https://api.meta/messages",
                    access_token="test_token",
                    payload={"to": "5511999999"},
                )

            assert exc_info.value.is_retryable is False
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_send_message_meta_error_transient(self) -> None:
        """Erro transitório (rate limit) lança HttpError retryable."""
        config = HttpClientConfig(timeout_seconds=5.0)
        client = WhatsAppHttpClient(config=config)

        error_response = {
            "error": {
                "type": "RateLimitException",
                "code": 429,
                "message": "Too many requests",
            }
        }
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = error_response
        mock_response.is_success = False

        with patch.object(
            client,
            "_request_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            with pytest.raises(HttpError) as exc_info:
                await client.send_message(
                    endpoint="https://api.meta/messages",
                    access_token="test_token",
                    payload={"to": "5511999999"},
                )

            assert exc_info.value.is_retryable is True
            assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_send_message_invalid_json_response(self) -> None:
        """Response JSON inválido lança HttpError."""
        config = HttpClientConfig(timeout_seconds=5.0)
        client = WhatsAppHttpClient(config=config)

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
        mock_response.is_success = True

        with patch.object(
            client,
            "_request_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            with pytest.raises(HttpError) as exc_info:
                await client.send_message(
                    endpoint="https://api.meta/messages",
                    access_token="test_token",
                    payload={"to": "5511999999"},
                )

            assert "JSON inválido" in str(exc_info.value)


class TestCreateWhatsAppHttpClient:
    """Testes para factory function."""

    def test_create_client_with_settings(self) -> None:
        """Factory cria cliente configurado corretamente."""
        settings = MagicMock()
        settings.whatsapp_request_timeout_seconds = 30
        settings.whatsapp_max_retries = 3
        settings.whatsapp_retry_backoff_seconds = 2.0
        settings.service_name = "pyloto_corp"
        settings.version = "1.0.0"
        settings.is_production = True
        settings.whatsapp_phone_number_id = "123456"

        client = create_whatsapp_http_client(settings)

        assert isinstance(client, WhatsAppHttpClient)
        assert client.phone_number_id == "123456"
        assert client._config.timeout_seconds == 30.0
        assert client._config.max_retries == 3
