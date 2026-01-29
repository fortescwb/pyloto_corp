"""Testes de segurança para webhook WhatsApp.

Conforme regras_e_padroes.md:
- Validação de assinatura X-Hub-Signature-256
- Rejeição de requests sem headers obrigatórios
- Proteção contra JSON malformado
- Verificação de token no endpoint GET
"""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pyloto_corp.api.app import create_app
from pyloto_corp.config.settings import get_settings

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "whatsapp" / "webhook"
WEBHOOK_SECRET = "test-webhook-secret-for-signature"
VERIFY_TOKEN = "test-verify-token"


def _compute_signature(payload: bytes, secret: str) -> str:
    """Computa assinatura HMAC SHA-256 no formato esperado pela Meta."""
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.fixture()
def client_with_secret(monkeypatch: pytest.MonkeyPatch):
    """Cliente de teste com webhook secret configurado."""
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", VERIFY_TOKEN)
    monkeypatch.setenv("WHATSAPP_WEBHOOK_SECRET", WEBHOOK_SECRET)
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def sample_payload() -> bytes:
    """Fixture de texto simples em bytes."""
    fixture_path = FIXTURES_DIR / "text.single.json"
    return fixture_path.read_bytes()


class TestSignatureValidation:
    """Testes de validação de assinatura X-Hub-Signature-256."""

    def test_valid_signature_accepted(
        self, client_with_secret: TestClient, sample_payload: bytes
    ):
        """Request com assinatura válida é aceito (200)."""
        signature = _compute_signature(sample_payload, WEBHOOK_SECRET)

        response = client_with_secret.post(
            "/webhooks/whatsapp",
            content=sample_payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["status"] == "enqueued"
        assert body["signature_validated"] is True
        assert body["signature_skipped"] is False
        assert body["inbound_event_id"]

    def test_invalid_signature_rejected(
        self, client_with_secret: TestClient, sample_payload: bytes
    ):
        """Request com assinatura errada é rejeitado (401)."""
        wrong_signature = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

        response = client_with_secret.post(
            "/webhooks/whatsapp",
            content=sample_payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": wrong_signature,
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "invalid_signature"

    def test_missing_signature_header_rejected(
        self, client_with_secret: TestClient, sample_payload: bytes
    ):
        """Request sem header X-Hub-Signature-256 é rejeitado (401)."""
        response = client_with_secret.post(
            "/webhooks/whatsapp",
            content=sample_payload,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "invalid_signature"

    def test_malformed_signature_format_rejected(
        self, client_with_secret: TestClient, sample_payload: bytes
    ):
        """Request com formato de assinatura inválido é rejeitado (401)."""
        # Sem o prefixo sha256=
        malformed = "abcdef1234567890"

        response = client_with_secret.post(
            "/webhooks/whatsapp",
            content=sample_payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": malformed,
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "invalid_signature"

    def test_empty_signature_rejected(
        self, client_with_secret: TestClient, sample_payload: bytes
    ):
        """Request com assinatura vazia é rejeitado (401)."""
        response = client_with_secret.post(
            "/webhooks/whatsapp",
            content=sample_payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "",
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "invalid_signature"


class TestVerifyTokenValidation:
    """Testes de validação do verify token no endpoint GET."""

    def test_valid_verify_token_returns_challenge(
        self, client_with_secret: TestClient
    ):
        """Verify token correto retorna o challenge (200)."""
        response = client_with_secret.get(
            "/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": VERIFY_TOKEN,
                "hub.challenge": "challenge-12345",
            },
        )

        assert response.status_code == 200
        assert response.text == "challenge-12345"

    def test_invalid_verify_token_rejected(self, client_with_secret: TestClient):
        """Verify token incorreto é rejeitado (403)."""
        response = client_with_secret.get(
            "/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "challenge-12345",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "verification_failed"

    def test_missing_verify_token_rejected(self, client_with_secret: TestClient):
        """Ausência de verify token é rejeitada (403)."""
        response = client_with_secret.get(
            "/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "challenge-12345",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "verification_failed"

    def test_wrong_hub_mode_rejected(self, client_with_secret: TestClient):
        """Modo diferente de 'subscribe' é rejeitado (403)."""
        response = client_with_secret.get(
            "/webhooks/whatsapp",
            params={
                "hub.mode": "unsubscribe",
                "hub.verify_token": VERIFY_TOKEN,
                "hub.challenge": "challenge-12345",
            },
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "verification_failed"


class TestJsonValidation:
    """Testes de validação de JSON no payload."""

    def test_invalid_json_rejected(self, client_with_secret: TestClient):
        """Payload com JSON inválido é rejeitado (400)."""
        invalid_json = b"{ this is not valid json }"
        signature = _compute_signature(invalid_json, WEBHOOK_SECRET)

        response = client_with_secret.post(
            "/webhooks/whatsapp",
            content=invalid_json,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "invalid_json"

    def test_empty_body_accepted(self, client_with_secret: TestClient):
        """Body vazio é tratado como {} (não falha)."""
        empty_body = b""
        signature = _compute_signature(empty_body, WEBHOOK_SECRET)

        response = client_with_secret.post(
            "/webhooks/whatsapp",
            content=empty_body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )

        # Pipeline deve aceitar, mesmo que não processe nada
        assert response.status_code == 200

    def test_truncated_json_rejected(self, client_with_secret: TestClient):
        """JSON truncado é rejeitado (400)."""
        truncated = b'{"object": "whatsapp_business_account", "entry": ['
        signature = _compute_signature(truncated, WEBHOOK_SECRET)

        response = client_with_secret.post(
            "/webhooks/whatsapp",
            content=truncated,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "invalid_json"


class TestEdgeCases:
    """Casos de borda e cenários de abuso."""

    def test_signature_without_secret_configured(self, monkeypatch: pytest.MonkeyPatch):
        """Quando secret não está configurado, assinatura é ignorada (skipped)."""
        monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", VERIFY_TOKEN)
        # Não definir WHATSAPP_WEBHOOK_SECRET
        monkeypatch.delenv("WHATSAPP_WEBHOOK_SECRET", raising=False)
        get_settings.cache_clear()

        app = create_app()
        with TestClient(app) as client:
            fixture_path = FIXTURES_DIR / "text.single.json"
            payload = fixture_path.read_bytes()

            # Sem assinatura - deve ser aceito quando secret não configurado
            response = client.post(
                "/webhooks/whatsapp",
                content=payload,
                headers={"Content-Type": "application/json"},
            )

            assert response.status_code == 200
            body = response.json()
            assert body["signature_validated"] is False
            assert body["signature_skipped"] is True

    def test_very_large_payload_with_valid_signature(
        self, client_with_secret: TestClient
    ):
        """Payload grande com assinatura válida é aceito."""
        # Criar payload grande mas válido
        large_payload = json.dumps({
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "BIZ_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "+55 11 99999-9999",
                                    "phone_number_id": "PHONE_ID",
                                },
                                "messages": [
                                    {
                                        "from": "5511888888888",
                                        "id": f"wamid.MSG_{i:05d}",
                                        "timestamp": "1700000000",
                                        "text": {"body": f"Mensagem {i} " + "x" * 100},
                                        "type": "text",
                                    }
                                    for i in range(10)  # 10 mensagens no batch
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }).encode("utf-8")

        signature = _compute_signature(large_payload, WEBHOOK_SECRET)

        response = client_with_secret.post(
            "/webhooks/whatsapp",
            content=large_payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )

        assert response.status_code == 200

    def test_tampered_payload_rejected(self, client_with_secret: TestClient):
        """Payload adulterado após assinatura é rejeitado."""
        original_payload = b'{"object": "whatsapp_business_account", "entry": []}'
        signature = _compute_signature(original_payload, WEBHOOK_SECRET)

        # Adultera o payload após gerar assinatura
        tampered = b'{"object": "whatsapp_business_account", "entry": [{"hacked": true}]}'

        response = client_with_secret.post(
            "/webhooks/whatsapp",
            content=tampered,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "invalid_signature"
