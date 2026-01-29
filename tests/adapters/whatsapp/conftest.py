"""Fixtures para testes do adapter WhatsApp."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from pyloto_corp.config.settings import Settings


@pytest.fixture(autouse=True)
def mock_whatsapp_outbound_http():
    """Mocka HTTP client e settings para todos os testes de outbound."""

    # 1. Mockar get_settings (importado localmente em _send_real)
    def fake_get_settings():
        settings = Settings()
        settings.whatsapp_phone_number_id = "1234567890"
        settings.whatsapp_access_token = "test-token-valid"
        settings.whatsapp_api_version = "v24.0"
        settings.whatsapp_api_base_url = "https://graph.facebook.com"
        return settings

    # 2. Mockar WhatsAppHttpClient.send_message para retornar resposta válida
    async def fake_send_message(endpoint: str, access_token: str, payload: dict):
        # Validar que endpoint não contém None
        assert "None" not in endpoint, f"Endpoint contém None: {endpoint}"
        assert access_token is not None, "Access token não pode ser None"

        # Retornar resposta fake válida
        return {"messages": [{"id": "wamid.TEST_MSG_ID_12345"}]}

    # Aplicar patches
    with (
        patch("pyloto_corp.config.settings.get_settings", side_effect=fake_get_settings),
        patch("pyloto_corp.adapters.whatsapp.http_client.WhatsAppHttpClient") as mock_client_class,
    ):
        mock_client = AsyncMock()
        mock_client.send_message = AsyncMock(side_effect=fake_send_message)
        mock_client_class.return_value = mock_client

        yield
