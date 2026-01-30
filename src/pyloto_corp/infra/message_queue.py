"""Interface de fila de mensagens para processamento assíncrono.

Abstrai a implementação de fila (Cloud Tasks, Pub/Sub, memória) permitindo
processamento desacoplado: webhook accept → enqueue → return 200 → workers processam.

Responsabilidades:
- Enfileirar payloads de webhook para processamento posterior
- Desenfileirar e processar em background workers
- Garantir at-least-once delivery e idempotência
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from pyloto_corp.observability.logging import get_logger

logger: logging.Logger = get_logger(__name__)


@dataclass
class QueuedMessage:
    """Mensagem enfileirada."""

    payload: dict[str, Any]
    task_id: str | None = None
    retry_count: int = 0
    max_retries: int = 3


class MessageQueueError(Exception):
    """Erro ao operar fila."""

    pass


class MessageQueue(ABC):
    """Contrato abstrato para fila de mensagens."""

    @abstractmethod
    async def enqueue(self, payload: dict[str, Any]) -> str:
        """Enfileira um payload e retorna task_id.

        Args:
            payload: Webhook payload do WhatsApp

        Returns:
            Task ID para rastreamento

        Raises:
            MessageQueueError: Se enfileiramento falhar
        """
        ...

    @abstractmethod
    async def dequeue(self, batch_size: int = 1) -> list[QueuedMessage]:
        """Desenfileira mensagens para processamento.

        Args:
            batch_size: Número máximo de mensagens a desenfileirar

        Returns:
            Lista de mensagens enfileiradas
        """
        ...

    @abstractmethod
    async def acknowledge(self, task_id: str) -> None:
        """Marca tarefa como processada com sucesso.

        Args:
            task_id: ID da tarefa a confirmar
        """
        ...

    @abstractmethod
    async def nack(self, task_id: str, error: str | None = None) -> None:
        """Marca tarefa como falhada para retry.

        Args:
            task_id: ID da tarefa
            error: Mensagem de erro (opcional)
        """
        ...


class InMemoryMessageQueue(MessageQueue):
    """Implementação em memória para dev/teste.

    ⚠️ NÃO use em produção (perde mensagens ao restart).
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[QueuedMessage] | None = None
        self._task_counter = 0

    async def _ensure_queue(self) -> None:
        """Cria queue lazily quando necessário (event loop ready)."""
        if self._queue is None:
            self._queue = asyncio.Queue()

    async def enqueue(self, payload: dict[str, Any]) -> str:
        """Enfileira payload em memória."""
        await self._ensure_queue()
        self._task_counter += 1
        task_id = f"mem-{self._task_counter}"
        msg = QueuedMessage(payload=payload, task_id=task_id)
        await self._queue.put(msg)
        logger.debug("enqueued_in_memory", extra={"task_id": task_id})
        return task_id

    async def dequeue(self, batch_size: int = 1) -> list[QueuedMessage]:
        """Desenfileira até batch_size mensagens."""
        await self._ensure_queue()
        messages = []
        for _ in range(batch_size):
            try:
                msg = self._queue.get_nowait()
                messages.append(msg)
            except asyncio.QueueEmpty:
                break
        return messages

    async def acknowledge(self, task_id: str) -> None:
        """Marca como sucesso."""
        logger.debug("acknowledged", extra={"task_id": task_id})

    async def nack(self, task_id: str, error: str | None = None) -> None:
        """Marca como falha (para retry posterior)."""
        logger.warning("nacked", extra={"task_id": task_id, "error": error})


class GoogleCloudTasksQueue(MessageQueue):
    """Implementação usando Google Cloud Tasks (produção).

    Requer:
    - GOOGLE_CLOUD_PROJECT configurado
    - CLOUDTASKS_QUEUE_NAME
    - Credenciais do GCP (Application Default Credentials)
    """

    def __init__(
        self,
        project: str,
        queue: str,
        location: str = "us-central1",
        handler_url: str = "http://localhost:8080/tasks/process",
        default_headers: dict[str, str] | None = None,
    ) -> None:
        """Inicializa cliente Cloud Tasks.

        Args:
            project: Google Cloud project ID
            queue: Nome da fila
            location: Região da fila (padrão: us-central1)
            handler_url: URL do endpoint que processa tarefas
            default_headers: Headers adicionais enviados nas tasks (ex.: token interno)
        """
        self._project = project
        self._queue = queue
        self._location = location
        self._handler_url = handler_url
        self._client = None
        self._default_headers = default_headers or {}

    def _get_client(self):
        """Lazy load do cliente Cloud Tasks."""
        if self._client is None:
            from google.cloud import tasks_v2

            self._client = tasks_v2.CloudTasksClient()
        return self._client

    async def enqueue(self, payload: dict[str, Any]) -> str:
        """Enfileira em Cloud Tasks."""
        try:
            client = self._get_client()
            parent = client.queue_path(self._project, self._location, self._queue)
            task = {
                "http_request": {
                    "http_method": "POST",
                    "url": self._handler_url,
                    "headers": {
                        "Content-Type": "application/json",
                        **self._default_headers,
                    },
                    "body": json.dumps(payload).encode(),
                }
            }
            response = client.create_task(request={"parent": parent, "task": task})
            task_id = response.name
            logger.debug(
                "enqueued_cloud_tasks",
                extra={"task_id": task_id, "queue": self._queue},
            )
            return task_id
        except Exception as e:
            raise MessageQueueError(f"Failed to enqueue in Cloud Tasks: {e}") from e

    async def dequeue(self, batch_size: int = 1) -> list[QueuedMessage]:
        """Cloud Tasks push tasks via HTTP, não pull.

        Este método não é usado para Cloud Tasks (push model).
        """
        logger.warning(
            "dequeue_not_applicable",
            extra={"reason": "Cloud Tasks uses push model"},
        )
        return []

    async def acknowledge(self, task_id: str) -> None:
        """Cloud Tasks reconhece automaticamente se status 200."""
        logger.debug("auto_acknowledged_cloud_tasks", extra={"task_id": task_id})

    async def nack(self, task_id: str, error: str | None = None) -> None:
        """Cloud Tasks retry automático (exponential backoff)."""
        logger.warning(
            "auto_retried_cloud_tasks",
            extra={"task_id": task_id, "error": error},
        )


def create_message_queue_from_settings(
    settings: Any,
    *,
    queue_name: str | None = None,
    handler_url: str | None = None,
    headers: dict[str, str] | None = None,
) -> MessageQueue:
    """Factory assíncrona para criar fila conforme configuração.

    Args:
        settings: Objeto Settings com QUEUE_BACKEND, GCP_PROJECT, etc.
        queue_name: Nome da fila (sobrepõe settings)
        handler_url: URL do handler (Cloud Tasks push)
        headers: Headers extras para a task (ex.: token interno)

    Returns:
        Instância de MessageQueue apropriada
    """
    backend = getattr(settings, "queue_backend", "memory").lower()

    if backend == "cloud_tasks":
        project = getattr(settings, "gcp_project", None)
        resolved_queue = queue_name or getattr(settings, "cloudtasks_queue_name", None)
        resolved_handler = handler_url or getattr(settings, "cloudtasks_handler_url", None)
        if not project or not resolved_queue:
            raise MessageQueueError(
                "queue_backend=cloud_tasks requires GCP_PROJECT and CLOUDTASKS_QUEUE_NAME"
            )
        if not resolved_handler:
            raise MessageQueueError("queue_backend=cloud_tasks requires handler_url configured")
        return GoogleCloudTasksQueue(
            project=project,
            queue=resolved_queue,
            location=getattr(settings, "cloudtasks_location", "us-central1"),
            handler_url=resolved_handler,
            default_headers=headers,
        )

    if backend == "memory":
        return InMemoryMessageQueue()

    raise MessageQueueError(f"Unsupported queue backend: {backend}")
