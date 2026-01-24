from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pyloto_corp.api.app import create_app
from pyloto_corp.config.settings import get_settings


def test_invalid_signature_returns_401(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "test-token")
    monkeypatch.setenv("WHATSAPP_WEBHOOK_SECRET", "secret")
    get_settings.cache_clear()

    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/webhooks/whatsapp",
            json={"entry": []},
            headers={"X-Hub-Signature-256": "sha256=deadbeef"},
        )

    assert response.status_code == 401
