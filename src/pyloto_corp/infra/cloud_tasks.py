"""Helper para criação de tasks HTTP no Google Cloud Tasks."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import anyio
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)


class CloudTaskDispatchError(Exception):
    """Erro ao criar task no Cloud Tasks."""


@dataclass(slots=True, frozen=True)
class TaskMetadata:
    """Metadados retornados após enqueue."""

    name: str
    queue: str
    schedule_time: datetime | None = None


def _serialize_payload(payload: Mapping[str, Any]) -> bytes:
    """Serializa payload para JSON bytes."""
    try:
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CloudTaskDispatchError("invalid_task_payload") from exc


def _build_url(base_url: str, endpoint: str) -> str:
    """Concatena base_url + endpoint garantindo / único."""
    if not base_url:
        raise CloudTaskDispatchError("internal_task_base_url_missing")

    base = base_url.rstrip("/")
    path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    return f"{base}{path}"


def _build_task(
    url: str,
    payload: Mapping[str, Any],
    headers: Mapping[str, str],
    schedule_time: datetime | None,
) -> tasks_v2.Task:
    """Monta objeto Task com HttpRequest JSON."""
    http_request = tasks_v2.HttpRequest(
        http_method=tasks_v2.HttpMethod.POST,
        url=url,
        headers={"Content-Type": "application/json", **dict(headers)},
        body=_serialize_payload(payload),
    )

    task = tasks_v2.Task(http_request=http_request)

    if schedule_time:
        ts = timestamp_pb2.Timestamp()
        ts.FromDatetime(schedule_time.astimezone(UTC))
        task.schedule_time = ts

    return task


class CloudTasksDispatcher:
    """Enfileia tasks HTTP em filas inbound/outbound."""

    def __init__(
        self,
        *,
        client: tasks_v2.CloudTasksClient,
        project: str,
        location: str,
        base_url: str,
        default_headers: Mapping[str, str] | None = None,
        inbound_queue: str,
        outbound_queue: str,
    ) -> None:
        if not project:
            raise ValueError("project obrigatório para Cloud Tasks")
        if not location:
            raise ValueError("location obrigatório para Cloud Tasks")

        self._client = client
        self._project = project
        self._location = location
        self._base_url = base_url
        self._headers = dict(default_headers or {})
        self._inbound_queue = inbound_queue
        self._outbound_queue = outbound_queue

    def _create_task(
        self,
        queue: str,
        endpoint: str,
        payload: Mapping[str, Any],
        schedule_time: datetime | None = None,
    ) -> TaskMetadata:
        """Cria task sincronicamente (usada por wrappers async)."""
        url = _build_url(self._base_url, endpoint)
        task = _build_task(url, payload, self._headers, schedule_time)

        try:
            parent = self._client.queue_path(self._project, self._location, queue)
            response = self._client.create_task(request={"parent": parent, "task": task})
            return TaskMetadata(name=response.name, queue=queue, schedule_time=schedule_time)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "cloud_tasks_enqueue_failed",
                extra={"queue": queue, "endpoint": endpoint, "error": type(exc).__name__},
            )
            raise CloudTaskDispatchError(str(exc)) from exc

    async def enqueue_inbound(
        self,
        payload: Mapping[str, Any],
        *,
        schedule_time: datetime | None = None,
    ) -> TaskMetadata:
        """Enfileia task para /internal/process_inbound."""
        return await anyio.to_thread.run_sync(
            self._create_task,
            self._inbound_queue,
            "/internal/process_inbound",
            payload,
            schedule_time,
        )

    async def enqueue_outbound(
        self,
        payload: Mapping[str, Any],
        *,
        schedule_time: datetime | None = None,
    ) -> TaskMetadata:
        """Enfileia task para /internal/process_outbound."""
        return await anyio.to_thread.run_sync(
            self._create_task,
            self._outbound_queue,
            "/internal/process_outbound",
            payload,
            schedule_time,
        )


class LocalCloudTasksClient:
    """Cliente em memória para dev/testes (não usar em prod)."""

    def __init__(self) -> None:
        self.created_tasks: list[dict[str, Any]] = []

    @staticmethod
    def queue_path(project: str, location: str, queue: str) -> str:  # pragma: no cover
        return f"projects/{project}/locations/{location}/queues/{queue}"

    def create_task(self, request: Mapping[str, Any]):
        parent = request["parent"]
        task_name = f"{parent}/tasks/local-{len(self.created_tasks) + 1}"
        self.created_tasks.append(
            {"parent": parent, "task": request.get("task"), "name": task_name}
        )
        return type("Task", (), {"name": task_name})
