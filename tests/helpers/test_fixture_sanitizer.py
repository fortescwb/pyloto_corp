"""Testes para o sanitizador de fixtures."""

from __future__ import annotations

from tests.helpers.fixture_sanitizer import (
    PLACEHOLDERS,
    sanitize_graph_response,
    sanitize_webhook_payload,
)


class TestSanitizeWebhookPayload:
    """Testes para sanitize_webhook_payload."""

    def test_sanitize_phone_numbers(self) -> None:
        """Deve sanitizar números de telefone."""
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "contacts": [{"wa_id": "5511999887766"}],
                                "messages": [{"from": "+55 11 99988-7766"}],
                            }
                        }
                    ]
                }
            ]
        }

        result = sanitize_webhook_payload(payload)

        contacts = result["entry"][0]["changes"][0]["value"]["contacts"]
        messages = result["entry"][0]["changes"][0]["value"]["messages"]
        assert contacts[0]["wa_id"] == PLACEHOLDERS["wa_id"]
        assert messages[0]["from"] == PLACEHOLDERS["from"]

    def test_sanitize_message_ids(self) -> None:
        """Deve sanitizar IDs de mensagem."""
        payload = {"messages": [{"id": "wamid.HBgMNTUxMTk5OTg4Nzc2NhUCABIYFjBBOTk5ODg3NzY2NQ=="}]}

        result = sanitize_webhook_payload(payload)

        assert result["messages"][0]["id"].startswith("wamid.MSG_ID_TEST_")

    def test_sanitize_timestamps(self) -> None:
        """Deve sanitizar timestamps."""
        payload = {"messages": [{"timestamp": "1699999999"}]}

        result = sanitize_webhook_payload(payload)

        assert result["messages"][0]["timestamp"] == PLACEHOLDERS["timestamp"]

    def test_sanitize_profile_names(self) -> None:
        """Deve sanitizar nomes de perfil."""
        payload = {
            "contacts": [
                {
                    "profile": {"name": "João Silva"},
                    "wa_id": "5511999887766",
                }
            ]
        }

        result = sanitize_webhook_payload(payload)

        assert result["contacts"][0]["profile"]["name"] == PLACEHOLDERS["contact_name"]

    def test_remove_access_token(self) -> None:
        """Deve remover access_token completamente."""
        payload = {"access_token": "EAABsbCS1iHgBA...", "data": "ok"}

        result = sanitize_webhook_payload(payload)

        assert "access_token" not in result
        assert result["data"] == "ok"

    def test_sanitize_urls(self) -> None:
        """Deve sanitizar URLs."""
        payload = {"media": {"url": "https://cdn.fbsbx.com/v/t59.2708-21/123456.jpeg"}}

        result = sanitize_webhook_payload(payload)

        assert result["media"]["url"].startswith("https://example.test/media/")

    def test_preserve_non_sensitive_data(self) -> None:
        """Deve preservar dados não sensíveis."""
        payload = {
            "object": "whatsapp_business_account",
            "type": "text",
            "text": {"body": "Mensagem de teste"},
        }

        result = sanitize_webhook_payload(payload)

        assert result["object"] == "whatsapp_business_account"
        assert result["type"] == "text"
        assert result["text"]["body"] == "Mensagem de teste"

    def test_deep_copy_isolation(self) -> None:
        """Deve criar cópia independente do payload original."""
        payload = {"messages": [{"from": "5511999887766"}]}
        original_value = payload["messages"][0]["from"]

        sanitize_webhook_payload(payload)

        assert payload["messages"][0]["from"] == original_value


class TestSanitizeGraphResponse:
    """Testes para sanitize_graph_response."""

    def test_sanitize_send_response(self) -> None:
        """Deve sanitizar resposta de envio."""
        response = {
            "messaging_product": "whatsapp",
            "contacts": [{"input": "5511999887766", "wa_id": "5511999887766"}],
            "messages": [{"id": "wamid.HBgMNTUxMTk5OTg4Nzc2NhUC..."}],
        }

        result = sanitize_graph_response(response)

        assert result["contacts"][0]["wa_id"] == PLACEHOLDERS["wa_id"]
        assert result["messages"][0]["id"].startswith("wamid.MSG_ID_TEST_")

    def test_sanitize_error_response(self) -> None:
        """Deve preservar estrutura de erro."""
        response = {
            "error": {
                "message": "(#131047) Re-engagement message",
                "type": "OAuthException",
                "code": 131047,
                "fbtrace_id": "AxY12345abcDEF",
            }
        }

        result = sanitize_graph_response(response)

        assert result["error"]["message"] == "(#131047) Re-engagement message"
        assert result["error"]["code"] == 131047
        # fbtrace_id é sanitizado (tem mais de 20 chars)
        assert result["error"]["fbtrace_id"] != "AxY12345abcDEF"

    def test_deterministic_ids(self) -> None:
        """IDs gerados devem ser determinísticos (reset por chamada)."""
        response = {"messages": [{"id": "wamid.ABC"}, {"id": "wamid.DEF"}]}

        result1 = sanitize_graph_response(response)
        result2 = sanitize_graph_response(response)

        # Mesma entrada deve gerar mesma saída
        assert result1["messages"][0]["id"] == result2["messages"][0]["id"]
        assert result1["messages"][1]["id"] == result2["messages"][1]["id"]
