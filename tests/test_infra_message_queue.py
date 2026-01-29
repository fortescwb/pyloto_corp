"""Testes da fila de mensagens assíncrona."""

import pytest

from pyloto_corp.infra.message_queue import InMemoryMessageQueue, QueuedMessage


@pytest.mark.asyncio
async def test_in_memory_queue_enqueue():
    """Testa enfileiramento em memória."""
    queue = InMemoryMessageQueue()
    payload = {"user_id": "123", "message": "Olá"}

    task_id = await queue.enqueue(payload)

    assert task_id is not None
    assert task_id.startswith("mem-")


@pytest.mark.asyncio
async def test_in_memory_queue_dequeue():
    """Testa desenfileiramento em memória."""
    queue = InMemoryMessageQueue()
    payload1 = {"msg": "msg1"}
    payload2 = {"msg": "msg2"}

    await queue.enqueue(payload1)
    await queue.enqueue(payload2)

    messages = await queue.dequeue(batch_size=2)

    assert len(messages) == 2
    assert messages[0].payload == payload1
    assert messages[1].payload == payload2


@pytest.mark.asyncio
async def test_in_memory_queue_dequeue_empty():
    """Testa desenfileiramento de fila vazia."""
    queue = InMemoryMessageQueue()

    messages = await queue.dequeue(batch_size=5)

    assert len(messages) == 0


@pytest.mark.asyncio
async def test_in_memory_queue_batch_dequeue_limit():
    """Testa limite de batch no desenfileiramento."""
    queue = InMemoryMessageQueue()

    for i in range(10):
        await queue.enqueue({"index": i})

    batch1 = await queue.dequeue(batch_size=3)
    batch2 = await queue.dequeue(batch_size=3)

    assert len(batch1) == 3
    assert len(batch2) == 3


@pytest.mark.asyncio
async def test_in_memory_queue_acknowledge():
    """Testa reconhecimento de tarefa."""
    queue = InMemoryMessageQueue()
    task_id = await queue.enqueue({"test": "data"})

    # Não deve lançar exceção
    await queue.acknowledge(task_id)


@pytest.mark.asyncio
async def test_in_memory_queue_nack():
    """Testa nack de tarefa (falha)."""
    queue = InMemoryMessageQueue()
    task_id = await queue.enqueue({"test": "data"})

    # Não deve lançar exceção
    await queue.nack(task_id, error="Test error")


@pytest.mark.asyncio
async def test_queue_fifo_order():
    """Testa ordem FIFO da fila."""
    queue = InMemoryMessageQueue()

    payloads = [{"order": i} for i in range(5)]
    for p in payloads:
        await queue.enqueue(p)

    messages = await queue.dequeue(batch_size=5)

    for i, msg in enumerate(messages):
        assert msg.payload["order"] == i


@pytest.mark.asyncio
async def test_queued_message_structure():
    """Testa estrutura de QueuedMessage."""
    payload = {"test": "data"}
    msg = QueuedMessage(payload=payload, task_id="test-1", retry_count=0)

    assert msg.payload == payload
    assert msg.task_id == "test-1"
    assert msg.retry_count == 0
    assert msg.max_retries == 3
