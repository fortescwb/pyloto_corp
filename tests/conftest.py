from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pyloto_corp.api.app import create_app
from pyloto_corp.config.settings import get_settings


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "test-token")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
