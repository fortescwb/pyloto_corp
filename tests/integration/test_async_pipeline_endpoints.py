from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from pyloto_corp.adapters.whatsapp.models import OutboundMessageResponse
from pyloto_corp.adapters.whatsapp.outbound import WhatsAppOutboundClient
from pyloto_corp.api.app import create_app
from pyloto_corp.config.settings import get_settings
from pyloto_corp.infra.cloud_tasks import CloudTaskDispatchError, TaskMetadata
from pyloto_corp.infra.dedupe import InMemoryDedupeStore
from pyloto_corp.infra.http import HttpError
from pyloto_corp.infra.inbound_processing_log import InboundProcessingLogStore
from pyloto_corp.infra.outbound_dedup_memory import InMemoryOutboundDedupeStore

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "whatsapp" / "webhook"
INTERNAL_TOKEN = "test-internal-token"
WEBHOOK_SECRET = "secret"


class CaptureDispatcher:
    """Dispatcher fake para capturar enqueues em testes."""

    def __init__(self) -> None:
        self.inbound: list[dict[str, Any]] = []
        self.outbound: list[dict[str, Any]] = []

    async def enqueue_inbound(self, payload: dict[str, Any], schedule_time=None):  # noqa: ANN001
        name = f"inbound-{len(self.inbound) + 1}"
        self.inbound.append({"payload": payload, "schedule_time": schedule_time})
        return TaskMetadata(name=name, queue="whatsapp-inbound", schedule_time=schedule_time)

    async def enqueue_outbound(self, payload: dict[str, Any], schedule_time=None):  # noqa: ANN001
        name = f"outbound-{len(self.outbound) + 1}"
        self.outbound.append({"payload": payload, "schedule_time": schedule_time})
        return TaskMetadata(name=name, queue="whatsapp-outbound", schedule_time=schedule_time)


class FakeTasksClient:
    """Mock de CloudTasksClient para capturar create_task."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    @staticmethod
    def queue_path(project: str, location: str, queue: str) -> str:  # pragma: no cover
        return f"projects/{project}/locations/{location}/queues/{queue}"

    def create_task(self, request: dict[str, Any]):
        self.requests.append(request)
        return type("Task", (), {"name": f"{request['parent']}/tasks/test-1"})


def _load_payload(filename: str) -> dict:
    return json.loads((FIXTURES_DIR / filename).read_text())


def _make_signature(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.fixture()
def app_with_internal_token(monkeypatch: pytest.MonkeyPatch):
    """Cria app com token interno e dispatcher fake."""
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-token")
    monkeypatch.setenv("WHATSAPP_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("INTERNAL_TASK_TOKEN", INTERNAL_TOKEN)
    get_settings.cache_clear()

    app = create_app()
    app.state.dedupe_store = InMemoryDedupeStore()
    app.state.outbound_dedupe_store = InMemoryOutboundDedupeStore()
    app.state.tasks_dispatcher = CaptureDispatcher()
    return app


@pytest.fixture()
def app_with_cloud_tasks(monkeypatch: pytest.MonkeyPatch):
    """App configurada para Cloud Tasks com client fake."""
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-token")
    monkeypatch.setenv("WHATSAPP_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("INTERNAL_TASK_TOKEN", INTERNAL_TOKEN)
    monkeypatch.setenv("CLOUD_TASKS_ENABLED", "true")
    monkeypatch.setenv("QUEUE_BACKEND", "cloud_tasks")
    monkeypatch.setenv("GCP_PROJECT", "test-project")
    monkeypatch.setenv("INTERNAL_TASK_BASE_URL", "https://internal.test")
    get_settings.cache_clear()

    fake_client = FakeTasksClient()
    monkeypatch.setattr(
        "pyloto_corp.infra.cloud_tasks.tasks_v2.CloudTasksClient",
        lambda: fake_client,
    )

    app = create_app()
    app.state.dedupe_store = InMemoryDedupeStore()
    app.state.cloud_tasks_client = fake_client
    return app, fake_client


def test_process_inbound_requires_token(app_with_internal_token):
    client = TestClient(app_with_internal_token)

    response = client.post("/internal/process_inbound", json={"payload": {}})

    assert response.status_code == 401
    assert response.json()["detail"] == "unauthorized_internal_call"


def test_process_inbound_enqueues_outbound(app_with_internal_token):
    client = TestClient(app_with_internal_token)
    dispatcher: CaptureDispatcher = app_with_internal_token.state.tasks_dispatcher

    payload = _load_payload("text.single.json")
    inbound_body = {
        "payload": payload,
        "correlation_id": "corr-1",
    }

    headers = {"X-Internal-Token": INTERNAL_TOKEN}

    response = client.post("/internal/process_inbound", json=inbound_body, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["processed"] == 1
    assert body["deduped"] == 0
    assert len(dispatcher.outbound) == 1
    outbound_payload = dispatcher.outbound[0]["payload"]
    expected_id = payload["entry"][0]["changes"][0]["value"]["messages"][0]["id"]
    assert outbound_payload["idempotency_key"] == expected_id


def test_process_outbound_enforces_token(app_with_internal_token):
    client = TestClient(app_with_internal_token)

    response = client.post("/internal/process_outbound", json={"to": "+5511"})

    assert response.status_code == 401
    assert response.json()["detail"] == "unauthorized_internal_call"


def test_process_outbound_retryable_then_success(
    app_with_internal_token, monkeypatch: pytest.MonkeyPatch
):
    client = TestClient(app_with_internal_token)

    responses: list[Exception | OutboundMessageResponse] = [
        HttpError("retry", status_code=503, is_retryable=True),
        OutboundMessageResponse(success=True, message_id="wa-999"),
    ]

    async def flaky_send(self, request):  # noqa: ANN001
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(WhatsAppOutboundClient, "send_message", flaky_send, raising=False)

    headers = {"X-Internal-Token": INTERNAL_TOKEN}
    payload = {
        "to": "5511888888888",
        "message_type": "text",
        "text": "retry me",
        "idempotency_key": "idemp-retry",
    }

    first = client.post("/internal/process_outbound", json=payload, headers=headers)
    assert first.status_code == 503
    assert first.json()["detail"] == "whatsapp_retryable_error"

    second = client.post("/internal/process_outbound", json=payload, headers=headers)
    assert second.status_code == 200
    body = second.json()
    assert body["status"] == "sent"
    assert body["message_id"] == "wa-999"


def test_webhook_creates_cloud_task(app_with_cloud_tasks):
    app, fake_client = app_with_cloud_tasks
    client = TestClient(app)
    payload = _load_payload("text.single.json")
    body = json.dumps(payload).encode()
    signature = _make_signature(WEBHOOK_SECRET, body)

    response = client.post(
        "/webhooks/whatsapp",
        data=body,
        headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    resp_body = response.json()
    assert resp_body["enqueued"] is True
    assert resp_body["task_name"]
    assert resp_body["inbound_event_id"]
    assert len(fake_client.requests) == 1
    request_created = fake_client.requests[0]
    assert request_created["parent"].endswith("/queues/whatsapp-inbound")
    task = request_created["task"]
    assert task.http_request.url.endswith("/internal/process_inbound")
    assert task.http_request.headers["X-Internal-Token"] == INTERNAL_TOKEN
    created_payload = json.loads(task.http_request.body.decode())
    assert created_payload["inbound_event_id"] == resp_body["inbound_event_id"]
    assert created_payload["correlation_id"] == resp_body["correlation_id"]


def test_webhook_dedupe_blocks_duplicate_enqueues(app_with_cloud_tasks):
    app, fake_client = app_with_cloud_tasks
    client = TestClient(app)
    payload = _load_payload("text.single.json")
    body = json.dumps(payload).encode()
    signature = _make_signature(WEBHOOK_SECRET, body)
    headers = {"X-Hub-Signature-256": signature, "Content-Type": "application/json"}

    first = client.post("/webhooks/whatsapp", data=body, headers=headers)
    assert first.status_code == 200
    second = client.post("/webhooks/whatsapp", data=body, headers=headers)
    assert second.status_code == 200

    assert first.json()["enqueued"] is True
    assert second.json()["enqueued"] is False
    assert len(fake_client.requests) == 1


def test_process_inbound_logs_and_persists(
    app_with_internal_token, caplog: pytest.LogCaptureFixture
):
    client = TestClient(app_with_internal_token)
    dispatcher: CaptureDispatcher = app_with_internal_token.state.tasks_dispatcher

    payload = _load_payload("text.single.json")
    inbound_body = {
        "payload": payload,
        "correlation_id": "corr-1",
    }
    mock_store = MagicMock(spec=InboundProcessingLogStore)
    app_with_internal_token.state.inbound_log_store = mock_store

    headers = {"X-Internal-Token": INTERNAL_TOKEN, "X-CloudTasks-TaskName": "task-1"}
    caplog.set_level("INFO")

    response = client.post("/internal/process_inbound", json=inbound_body, headers=headers)
    assert response.status_code == 200
    expected_id = payload["entry"][0]["changes"][0]["value"]["messages"][0]["id"]
    mock_store.mark_started.assert_called_once_with(expected_id, "corr-1", "task-1")
    mock_store.mark_finished.assert_called_once_with(
        expected_id,
        correlation_id="corr-1",
        task_name="task-1",
        enqueued_outbound=True,
        error=None,
    )
    assert any("inbound_processing_started" in record.message for record in caplog.records)
    assert any("inbound_processing_finished" in record.message for record in caplog.records)
    assert len(dispatcher.outbound) == 1


def test_webhook_enqueue_failure_returns_error(
    app_with_internal_token, monkeypatch: pytest.MonkeyPatch
):
    client = TestClient(app_with_internal_token)
    payload = _load_payload("text.single.json")
    body = json.dumps(payload).encode()
    signature = _make_signature(WEBHOOK_SECRET, body)

    class FailingDispatcher(CaptureDispatcher):
        async def enqueue_inbound(self, payload: dict[str, Any], schedule_time=None):  # noqa: ANN001
            raise CloudTaskDispatchError("boom")

    failing = FailingDispatcher()
    app_with_internal_token.state.tasks_dispatcher = failing
    dedupe_store: InMemoryDedupeStore = app_with_internal_token.state.dedupe_store

    response = client.post(
        "/webhooks/whatsapp",
        data=body,
        headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "enqueue_failed"
    assert not dedupe_store.is_duplicate(
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["id"]
    )
