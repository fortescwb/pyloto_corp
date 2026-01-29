"""Testes unitários para OutboundDedupeStore — idempotência de outbound."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from pyloto_corp.application.services.dedup_service import (
    generate_idempotency_key,
    hash_message_content,
)
from pyloto_corp.domain.outbound_dedup import (
    OutboundDedupeError,
    OutboundDedupeStore,
)
from pyloto_corp.infra.outbound_dedup_factory import create_outbound_dedupe_store
from pyloto_corp.infra.outbound_dedup_firestore import FirestoreOutboundDedupeStore
from pyloto_corp.infra.outbound_dedup_memory import InMemoryOutboundDedupeStore
from pyloto_corp.infra.outbound_dedup_redis import RedisOutboundDedupeStore

DEFAULT_TTL_SECONDS = OutboundDedupeStore.DEFAULT_TTL_SECONDS


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def in_memory_store() -> InMemoryOutboundDedupeStore:
    """Store em memória para testes."""
    return InMemoryOutboundDedupeStore()


@pytest.fixture
def mock_redis() -> MagicMock:
    """Mock de cliente Redis."""
    return MagicMock()


@pytest.fixture
def mock_firestore() -> MagicMock:
    """Mock de cliente Firestore."""
    mock = MagicMock()
    mock.collection.return_value.document.return_value.get.return_value.exists = False
    return mock


@pytest.fixture
def sample_message_content() -> dict[str, Any]:
    """Conteúdo de mensagem de exemplo."""
    return {
        "type": "text",
        "text": {"body": "Olá, tudo bem?"},
    }


# ============================================================
# Testes: Funções Auxiliares
# ============================================================


class TestGenerateIdempotencyKey:
    """Testes para geração de chave de idempotência."""

    def test_same_input_same_key(self) -> None:
        """Mesma entrada deve gerar mesma chave."""
        key1 = generate_idempotency_key("recipient_123", "hash_abc")
        key2 = generate_idempotency_key("recipient_123", "hash_abc")

        assert key1 == key2

    def test_different_recipient_different_key(self) -> None:
        """Destinatários diferentes devem gerar chaves diferentes."""
        key1 = generate_idempotency_key("recipient_123", "hash_abc")
        key2 = generate_idempotency_key("recipient_456", "hash_abc")

        assert key1 != key2

    def test_different_content_different_key(self) -> None:
        """Conteúdos diferentes devem gerar chaves diferentes."""
        key1 = generate_idempotency_key("recipient_123", "hash_abc")
        key2 = generate_idempotency_key("recipient_123", "hash_xyz")

        assert key1 != key2

    def test_key_is_sha256_hex(self) -> None:
        """Chave deve ser hash SHA256 em hex."""
        key = generate_idempotency_key("recipient", "content_hash")

        assert len(key) == 64  # SHA256 hex = 64 chars
        assert all(c in "0123456789abcdef" for c in key)


class TestHashMessageContent:
    """Testes para hash de conteúdo de mensagem."""

    def test_same_content_same_hash(
        self,
        sample_message_content: dict[str, Any],
    ) -> None:
        """Mesmo conteúdo deve gerar mesmo hash."""
        hash1 = hash_message_content(sample_message_content)
        hash2 = hash_message_content(sample_message_content)

        assert hash1 == hash2

    def test_different_content_different_hash(self) -> None:
        """Conteúdos diferentes devem gerar hashes diferentes."""
        content1 = {"type": "text", "text": {"body": "Olá"}}
        content2 = {"type": "text", "text": {"body": "Tchau"}}

        hash1 = hash_message_content(content1)
        hash2 = hash_message_content(content2)

        assert hash1 != hash2

    def test_order_independent_hash(self) -> None:
        """Ordem das chaves não deve afetar o hash."""
        content1 = {"a": 1, "b": 2}
        content2 = {"b": 2, "a": 1}

        hash1 = hash_message_content(content1)
        hash2 = hash_message_content(content2)

        assert hash1 == hash2


# ============================================================
# Testes: InMemoryOutboundDedupeStore
# ============================================================


class TestInMemoryOutboundDedupeStore:
    """Testes para store em memória."""

    def test_check_and_mark_new_message(
        self,
        in_memory_store: InMemoryOutboundDedupeStore,
    ) -> None:
        """Nova mensagem não deve ser duplicata."""
        result = in_memory_store.check_and_mark("key_123", "msg_abc")

        assert result.is_duplicate is False
        assert result.original_message_id is None

    def test_check_and_mark_duplicate(
        self,
        in_memory_store: InMemoryOutboundDedupeStore,
    ) -> None:
        """Segunda chamada com mesma chave deve ser duplicata."""
        in_memory_store.check_and_mark("key_123", "msg_abc")
        result = in_memory_store.check_and_mark("key_123", "msg_def")

        assert result.is_duplicate is True
        assert result.original_message_id == "msg_abc"
        assert result.original_timestamp is not None

    def test_is_sent_returns_true_after_mark(
        self,
        in_memory_store: InMemoryOutboundDedupeStore,
    ) -> None:
        """is_sent deve retornar True após marcar."""
        assert in_memory_store.is_sent("key_123") is False

        in_memory_store.check_and_mark("key_123", "msg_abc")
        in_memory_store.mark_sent("key_123", "msg_abc")

        assert in_memory_store.is_sent("key_123") is True

    def test_mark_sent_returns_false_if_exists(
        self,
        in_memory_store: InMemoryOutboundDedupeStore,
    ) -> None:
        """mark_sent deve retornar False se já existe."""
        assert in_memory_store.mark_sent("key_123", "msg_abc") is True
        assert in_memory_store.mark_sent("key_123", "msg_def") is False

    def test_expired_entry_not_duplicate(
        self,
        in_memory_store: InMemoryOutboundDedupeStore,
    ) -> None:
        """Entrada expirada não deve ser considerada duplicata."""
        # Marcar com TTL de 0 segundos (expira imediatamente)
        in_memory_store.check_and_mark("key_123", "msg_abc", ttl_seconds=0)

        # Forçar cleanup (simular tempo passado)
        import time

        time.sleep(0.01)  # Pequeno delay

        # Nova mensagem não deve ser duplicata após expiração
        # Note: em memória, cleanup acontece no próximo check
        in_memory_store._store["key_123"] = (
            "msg_abc",
            datetime.now(tz=UTC),
            datetime.now(tz=UTC).timestamp() - 1,  # Já expirou
        )

        result = in_memory_store.check_and_mark("key_123", "msg_def")
        assert result.is_duplicate is False


# ============================================================
# Testes: RedisOutboundDedupeStore
# ============================================================


class TestRedisOutboundDedupeStore:
    """Testes para store Redis."""

    def test_check_and_mark_new_message(self, mock_redis: MagicMock) -> None:
        """Nova mensagem com SETNX bem-sucedido."""
        mock_redis.set.return_value = True  # SETNX sucesso

        store = RedisOutboundDedupeStore(mock_redis)
        result = store.check_and_mark("key_123", "msg_abc")

        assert result.is_duplicate is False
        mock_redis.set.assert_called_once()

    def test_check_and_mark_duplicate(self, mock_redis: MagicMock) -> None:
        """Mensagem duplicada com SETNX falho."""
        mock_redis.set.return_value = False  # SETNX falha (já existe)
        mock_redis.get.return_value = json.dumps({
            "message_id": "msg_original",
            "timestamp": "2026-01-25T18:00:00+00:00",
        })

        store = RedisOutboundDedupeStore(mock_redis)
        result = store.check_and_mark("key_123", "msg_abc")

        assert result.is_duplicate is True
        assert result.original_message_id == "msg_original"

    def test_redis_error_raises_exception(self, mock_redis: MagicMock) -> None:
        """Erro de Redis deve levantar OutboundDedupeError."""
        mock_redis.set.side_effect = Exception("Redis connection failed")

        store = RedisOutboundDedupeStore(mock_redis)

        with pytest.raises(OutboundDedupeError, match="Redis unavailable"):
            store.check_and_mark("key_123", "msg_abc")

    def test_is_sent_uses_exists(self, mock_redis: MagicMock) -> None:
        """is_sent deve usar EXISTS do Redis."""
        mock_redis.exists.return_value = True
        mock_redis.get.return_value = json.dumps(
            {
                "status": "sent",
                "message_id": "msg_abc",
                "timestamp": datetime.now(tz=UTC).isoformat(),
            }
        )

        store = RedisOutboundDedupeStore(mock_redis)
        result = store.is_sent("key_123")

        assert result is True
        mock_redis.exists.assert_called_with("outbound:key_123")

    def test_custom_key_prefix(self, mock_redis: MagicMock) -> None:
        """Prefixo customizado deve ser usado."""
        mock_redis.set.return_value = True

        store = RedisOutboundDedupeStore(mock_redis, key_prefix="custom:")
        store.check_and_mark("key_123", "msg_abc")

        # Verificar que usou prefixo custom
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == "custom:key_123"


# ============================================================
# Testes: FirestoreOutboundDedupeStore
# ============================================================


class TestFirestoreOutboundDedupeStore:
    """Testes para store Firestore."""

    def test_check_and_mark_new_message(self, mock_firestore: MagicMock) -> None:
        """Nova mensagem com documento inexistente."""
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_firestore.collection.return_value.document.return_value.get.return_value = (
            mock_doc
        )

        store = FirestoreOutboundDedupeStore(mock_firestore)
        result = store.check_and_mark("key_123", "msg_abc")

        assert result.is_duplicate is False
        mock_firestore.collection.return_value.document.return_value.set.assert_called()

    def test_check_and_mark_duplicate(self, mock_firestore: MagicMock) -> None:
        """Mensagem duplicata com documento existente."""
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "message_id": "msg_original",
            "timestamp": datetime.now(tz=UTC),
            "_ttl_expire_at": datetime.now(tz=UTC) + timedelta(hours=24),
        }
        mock_firestore.collection.return_value.document.return_value.get.return_value = (
            mock_doc
        )

        store = FirestoreOutboundDedupeStore(mock_firestore)
        result = store.check_and_mark("key_123", "msg_abc")

        assert result.is_duplicate is True
        assert result.original_message_id == "msg_original"

    def test_expired_document_not_duplicate(self, mock_firestore: MagicMock) -> None:
        """Documento expirado não deve ser duplicata."""
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "message_id": "msg_old",
            "timestamp": datetime.now(tz=UTC) - timedelta(days=2),
            "_ttl_expire_at": datetime.now(tz=UTC) - timedelta(hours=1),  # Expirou
        }
        mock_firestore.collection.return_value.document.return_value.get.return_value = (
            mock_doc
        )

        store = FirestoreOutboundDedupeStore(mock_firestore)
        result = store.check_and_mark("key_123", "msg_new")

        assert result.is_duplicate is False

    def test_firestore_error_raises_exception(self, mock_firestore: MagicMock) -> None:
        """Erro de Firestore deve levantar OutboundDedupeError."""
        mock_firestore.collection.return_value.document.return_value.get.side_effect = (
            Exception("Firestore unavailable")
        )

        store = FirestoreOutboundDedupeStore(mock_firestore)

        with pytest.raises(OutboundDedupeError, match="Firestore unavailable"):
            store.check_and_mark("key_123", "msg_abc")


# ============================================================
# Testes: Factory
# ============================================================


class TestCreateOutboundDedupeStore:
    """Testes para factory function."""

    def test_create_memory_store(self) -> None:
        """Factory deve criar store em memória."""
        store = create_outbound_dedupe_store("memory")
        assert isinstance(store, InMemoryOutboundDedupeStore)

    def test_create_redis_store(self, mock_redis: MagicMock) -> None:
        """Factory deve criar store Redis."""
        store = create_outbound_dedupe_store("redis", redis_client=mock_redis)
        assert isinstance(store, RedisOutboundDedupeStore)

    def test_create_firestore_store(self, mock_firestore: MagicMock) -> None:
        """Factory deve criar store Firestore."""
        store = create_outbound_dedupe_store("firestore", firestore_client=mock_firestore)
        assert isinstance(store, FirestoreOutboundDedupeStore)

    def test_redis_without_client_raises(self) -> None:
        """Factory sem cliente Redis deve falhar."""
        with pytest.raises(ValueError, match="redis_client required"):
            create_outbound_dedupe_store("redis")

    def test_firestore_without_client_raises(self) -> None:
        """Factory sem cliente Firestore deve falhar."""
        with pytest.raises(ValueError, match="firestore_client required"):
            create_outbound_dedupe_store("firestore")

    def test_unknown_backend_raises(self) -> None:
        """Backend desconhecido deve falhar."""
        with pytest.raises(ValueError, match="Unknown outbound dedupe backend"):
            create_outbound_dedupe_store("unknown")


# ============================================================
# Testes: Edge Cases
# ============================================================


class TestOutboundDedupeEdgeCases:
    """Testes de casos de borda."""

    def test_empty_idempotency_key(
        self,
        in_memory_store: InMemoryOutboundDedupeStore,
    ) -> None:
        """Chave vazia deve funcionar."""
        result = in_memory_store.check_and_mark("", "msg_abc")
        assert result.is_duplicate is False

    def test_very_long_key(
        self,
        in_memory_store: InMemoryOutboundDedupeStore,
    ) -> None:
        """Chave muito longa deve funcionar."""
        long_key = "a" * 1000
        result = in_memory_store.check_and_mark(long_key, "msg_abc")
        assert result.is_duplicate is False

    def test_unicode_in_content_hash(self) -> None:
        """Conteúdo com Unicode deve gerar hash válido."""
        content = {"text": "Olá, mundo! 🌍 日本語"}
        hash_value = hash_message_content(content)

        assert len(hash_value) == 64

    def test_concurrent_checks(
        self,
        in_memory_store: InMemoryOutboundDedupeStore,
    ) -> None:
        """Múltiplas verificações com mesma chave."""
        results = [
            in_memory_store.check_and_mark("key_same", f"msg_{i}")
            for i in range(5)
        ]

        # Apenas a primeira não é duplicata
        assert results[0].is_duplicate is False
        assert all(r.is_duplicate is True for r in results[1:])
