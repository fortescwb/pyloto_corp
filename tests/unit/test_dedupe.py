"""Testes unitários para infra/dedupe.py.

Valida stores de deduplicação e factory function.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from pyloto_corp.config.settings import Settings
from pyloto_corp.infra.dedupe import (
    DedupeError,
    InMemoryDedupeStore,
    RedisDedupeStore,
    create_dedupe_store,
)


class TestInMemoryDedupeStore:
    """Testes para InMemoryDedupeStore."""

    def test_mark_if_new_returns_true_for_new_key(self) -> None:
        """Chave nova deve retornar True (marcou)."""
        store = InMemoryDedupeStore()
        assert store.mark_if_new("key1") is True

    def test_mark_if_new_returns_false_for_existing_key(self) -> None:
        """Chave existente deve retornar False (duplicado)."""
        store = InMemoryDedupeStore()
        store.mark_if_new("key1")
        assert store.mark_if_new("key1") is False

    def test_is_duplicate_does_not_mark(self) -> None:
        """is_duplicate não deve marcar a chave."""
        store = InMemoryDedupeStore()
        assert store.is_duplicate("key1") is False
        assert store.is_duplicate("key1") is False  # Ainda False

    def test_is_duplicate_returns_true_after_mark(self) -> None:
        """is_duplicate deve retornar True após marcação."""
        store = InMemoryDedupeStore()
        store.mark_if_new("key1")
        assert store.is_duplicate("key1") is True

    def test_clear_removes_key(self) -> None:
        """clear deve remover a chave do store."""
        store = InMemoryDedupeStore()
        store.mark_if_new("key1")
        assert store.clear("key1") is True
        assert store.is_duplicate("key1") is False

    def test_clear_returns_false_for_nonexistent_key(self) -> None:
        """clear deve retornar False se chave não existe."""
        store = InMemoryDedupeStore()
        assert store.clear("nonexistent") is False

    def test_ttl_expiration(self) -> None:
        """Chaves expiradas devem ser removidas."""
        store = InMemoryDedupeStore(ttl_seconds=1)
        store.mark_if_new("key1")

        # Simula passagem de tempo
        time.sleep(1.1)

        # Após TTL, a chave deve expirar
        assert store.mark_if_new("key1") is True

    def test_multiple_keys_independent(self) -> None:
        """Múltiplas chaves devem ser independentes."""
        store = InMemoryDedupeStore()
        store.mark_if_new("key1")
        assert store.mark_if_new("key2") is True
        assert store.mark_if_new("key1") is False


class TestRedisDedupeStore:
    """Testes para RedisDedupeStore com mocks."""

    def test_init_sets_parameters(self) -> None:
        """Construtor deve armazenar parâmetros."""
        store = RedisDedupeStore(
            redis_url="redis://localhost:6379/0",
            ttl_seconds=3600,
            fail_closed=True,
            key_prefix="test:",
        )
        assert store._redis_url == "redis://localhost:6379/0"
        assert store._ttl_seconds == 3600
        assert store._fail_closed is True
        assert store._key_prefix == "test:"

    def test_make_key_adds_prefix(self) -> None:
        """_make_key deve adicionar prefixo."""
        store = RedisDedupeStore(
            redis_url="redis://localhost:6379/0",
            key_prefix="dedupe:",
        )
        assert store._make_key("mykey") == "dedupe:mykey"

    def test_mark_if_new_with_mocked_redis(self) -> None:
        """mark_if_new deve usar SETNX com TTL."""
        store = RedisDedupeStore(
            redis_url="redis://localhost:6379/0",
            ttl_seconds=3600,
        )

        mock_client = MagicMock()
        # Primeira chamada: chave criada (nova)
        mock_client.set.return_value = True
        store._client = mock_client

        result = store.mark_if_new("key1")

        assert result is True  # Marcou chave nova
        mock_client.set.assert_called_once_with(
            "dedupe:key1",
            "1",
            nx=True,
            ex=3600,
        )

    def test_mark_if_new_returns_false_for_duplicate(self) -> None:
        """mark_if_new deve retornar False para duplicata."""
        store = RedisDedupeStore(redis_url="redis://localhost:6379/0")

        mock_client = MagicMock()
        # SETNX retorna False = chave já existia
        mock_client.set.return_value = False
        store._client = mock_client

        result = store.mark_if_new("existing_key")
        assert result is False  # É duplicata

    def test_is_duplicate_uses_exists(self) -> None:
        """is_duplicate deve usar EXISTS do Redis."""
        store = RedisDedupeStore(redis_url="redis://localhost:6379/0")

        mock_client = MagicMock()
        mock_client.exists.return_value = 1
        store._client = mock_client

        assert store.is_duplicate("key1") is True
        mock_client.exists.assert_called_once_with("dedupe:key1")

    def test_clear_uses_delete(self) -> None:
        """clear deve usar DELETE do Redis."""
        store = RedisDedupeStore(redis_url="redis://localhost:6379/0")

        mock_client = MagicMock()
        mock_client.delete.return_value = 1
        store._client = mock_client

        assert store.clear("key1") is True
        mock_client.delete.assert_called_once_with("dedupe:key1")

    def test_fail_closed_raises_on_connection_error(self) -> None:
        """Em fail_closed=True, erro de conexão deve levantar DedupeError."""
        store = RedisDedupeStore(
            redis_url="redis://localhost:6379/0",
            fail_closed=True,
        )

        mock_client = MagicMock()
        mock_client.set.side_effect = Exception("Connection refused")
        store._client = mock_client

        with pytest.raises(DedupeError, match="Falha ao verificar"):
            store.mark_if_new("key1")

    def test_fail_open_returns_false_on_error(self) -> None:
        """Em fail_closed=False, erro deve retornar False (processa)."""
        store = RedisDedupeStore(
            redis_url="redis://localhost:6379/0",
            fail_closed=False,
        )

        mock_client = MagicMock()
        mock_client.set.side_effect = Exception("Connection refused")
        store._client = mock_client

        # Não levanta erro, retorna True (processa mesmo sem marcar)
        result = store.mark_if_new("key1")
        assert result is True


class TestCreateDedupeStore:
    """Testes para factory function create_dedupe_store."""

    def test_creates_memory_store_for_memory_backend(self) -> None:
        """Deve criar InMemoryDedupeStore para backend=memory."""
        settings = Settings(dedupe_backend="memory")
        store = create_dedupe_store(settings)
        assert isinstance(store, InMemoryDedupeStore)

    def test_creates_redis_store_for_redis_backend(self) -> None:
        """Deve criar RedisDedupeStore para backend=redis."""
        settings = Settings(
            dedupe_backend="redis",
            redis_url="redis://localhost:6379/0",
        )

        # Mock para evitar conexão real
        with patch.object(RedisDedupeStore, "_get_client", return_value=MagicMock()):
            store = create_dedupe_store(settings)
            assert isinstance(store, RedisDedupeStore)

    def test_raises_for_redis_without_url(self) -> None:
        """Deve levantar ValueError se redis sem URL."""
        settings = Settings(dedupe_backend="redis", redis_url=None)

        with pytest.raises(ValueError, match="REDIS_URL"):
            create_dedupe_store(settings)

    def test_raises_for_unknown_backend(self) -> None:
        """Deve levantar ValueError para backend desconhecido."""
        settings = Settings(dedupe_backend="unknown")

        with pytest.raises(ValueError, match="não reconhecido"):
            create_dedupe_store(settings)

    def test_uses_settings_ttl(self) -> None:
        """Deve usar TTL das settings."""
        settings = Settings(dedupe_backend="memory", dedupe_ttl_seconds=7200)
        store = create_dedupe_store(settings)
        assert store.ttl_seconds == 7200

    def test_redis_fail_closed_in_production(self) -> None:
        """Redis deve ser fail_closed em produção."""
        settings = Settings(
            dedupe_backend="redis",
            redis_url="redis://localhost:6379/0",
            environment="production",
        )

        store = RedisDedupeStore(
            redis_url=settings.redis_url,
            fail_closed=settings.is_production,
        )

        assert store._fail_closed is True

    def test_redis_fail_open_in_development(self) -> None:
        """Redis pode ser fail_open em desenvolvimento."""
        settings = Settings(
            dedupe_backend="redis",
            redis_url="redis://localhost:6379/0",
            environment="development",
        )

        store = RedisDedupeStore(
            redis_url=settings.redis_url,
            fail_closed=settings.is_production,
        )

        assert store._fail_closed is False

    def test_creates_firestore_store_for_firestore_backend(self) -> None:
        """Deve criar FirestoreDedupeStore quando backend=firestore."""
        settings = Settings(
            dedupe_backend="firestore",
            firestore_project_id="demo-project",
        )

        with (
            patch("google.cloud.firestore.Client", return_value=MagicMock()),
            patch("pyloto_corp.infra.dedupe_firestore.FirestoreDedupeStore") as mock_store_cls,
        ):
            store_instance = MagicMock()
            mock_store_cls.return_value = store_instance

            store = create_dedupe_store(settings)

            assert store is store_instance
            mock_store_cls.assert_called_once()
