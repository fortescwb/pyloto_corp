from __future__ import annotations

import json
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "whatsapp_inbound.json"


def test_webhook_verification(client):
    response = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test-token",
            "hub.challenge": "challenge-123",
        },
    )
    assert response.status_code == 200
    assert response.text == "challenge-123"


def test_webhook_post_smoke(client):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    response = client.post("/webhooks/whatsapp", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "result" in body
