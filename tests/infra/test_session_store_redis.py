"""Testes para SessionStore baseado em Redis."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from pyloto_corp.application.session import SessionState
from pyloto_corp.domain.enums import Outcome
from pyloto_corp.domain.intent_queue import IntentQueue
from pyloto_corp.domain.models import LeadProfile
from pyloto_corp.infra.session_contract import SessionStoreError
from pyloto_corp.infra.session_store_redis import RedisSessionStore


class TestRedisSessionStoreSave:
    """Testes para método save."""

    def _create_mock_session(self, session_id: str = "test-session-123") -> SessionState:
        """Cria uma sessão de teste válida."""
        return SessionState(
            session_id=session_id,
            lead_profile=LeadProfile(phone="+5511987654321", name="Test User"),
            intent_queue=IntentQueue(),
            outcome=Outcome.AWAITING_USER,
        )

    def test_save_session_success(self):
        """Deve salvar sessão com TTL no Redis."""
        mock_redis = MagicMock()
        store = RedisSessionStore(mock_redis)
        session = self._create_mock_session()

        store.save(session, ttl_seconds=3600)

        expected_key = "session:test-session-123"
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == expected_key
        assert call_args[0][1] == 3600
        assert isinstance(call_args[0][2], str)  # JSON payload

    def test_save_session_default_ttl(self):
        """Deve usar TTL padrão (7200 segundos) se não especificado."""
        mock_redis = MagicMock()
        store = RedisSessionStore(mock_redis)
        session = self._create_mock_session()

        store.save(session)

        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 7200  # TTL padrão

    def test_save_session_serializable(self):
        """Deve serializar sessão como JSON válido."""
        mock_redis = MagicMock()
        store = RedisSessionStore(mock_redis)
        session = self._create_mock_session()

        store.save(session)

        call_args = mock_redis.setex.call_args
        payload_json = call_args[0][2]

        # Deve ser JSON válido
        data = json.loads(payload_json)
        assert data["session_id"] == "test-session-123"
        assert data["lead_profile"]["phone"] == "+5511987654321"

    def test_save_session_redis_error(self):
        """Deve lançar SessionStoreError se Redis falhar."""
        mock_redis = MagicMock()
        mock_redis.setex.side_effect = Exception("Redis connection failed")

        store = RedisSessionStore(mock_redis)
        session = self._create_mock_session()

        with pytest.raises(SessionStoreError):
            store.save(session)

    def test_save_session_key_format(self):
        """Deve usar formato correto de chave."""
        mock_redis = MagicMock()
        store = RedisSessionStore(mock_redis)
        session = self._create_mock_session(session_id="abc-123-xyz")

        store.save(session)

        call_args = mock_redis.setex.call_args
        key = call_args[0][0]
        assert key == "session:abc-123-xyz"


class TestRedisSessionStoreLoad:
    """Testes para método load."""

    def _create_session_json(self, session_id: str = "test-session-123") -> str:
        """Cria JSON de sessão de teste."""
        session = SessionState(
            session_id=session_id,
            lead_profile=LeadProfile(phone="+5511987654321", name="Test User"),
            intent_queue=IntentQueue(),
            outcome=Outcome.AWAITING_USER,
        )
        return session.model_dump_json()

    def test_load_session_success(self):
        """Deve carregar sessão válida do Redis."""
        mock_redis = MagicMock()
        session_json = self._create_session_json()
        mock_redis.get.return_value = session_json

        store = RedisSessionStore(mock_redis)
        result = store.load("test-session-123")

        assert result is not None
        assert result.session_id == "test-session-123"
        assert result.lead_profile.phone == "+5511987654321"
        mock_redis.get.assert_called_once_with("session:test-session-123")

    def test_load_session_success_bytes(self):
        """Deve carregar sessão retornada como bytes (Redis client)."""
        mock_redis = MagicMock()
        session_json = self._create_session_json()
        mock_redis.get.return_value = session_json.encode("utf-8")

        store = RedisSessionStore(mock_redis)
        result = store.load("test-session-123")

        assert result is not None
        assert result.session_id == "test-session-123"

    def test_load_session_not_found(self):
        """Deve retornar None se sessão não existe."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        store = RedisSessionStore(mock_redis)
        result = store.load("nonexistent-session")

        assert result is None

    def test_load_session_invalid_json(self):
        """Deve retornar None para JSON inválido."""
        mock_redis = MagicMock()
        mock_redis.get.return_value = "invalid json {{"

        store = RedisSessionStore(mock_redis)
        result = store.load("corrupted-session")

        assert result is None

    def test_load_session_redis_error(self):
        """Deve retornar None e fazer log se Redis falhar."""
        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("Redis connection error")

        store = RedisSessionStore(mock_redis)
        result = store.load("test-session")

        assert result is None

    def test_load_session_key_format(self):
        """Deve buscar com formato correto de chave."""
        mock_redis = MagicMock()
        session_json = self._create_session_json(session_id="abc-123")
        mock_redis.get.return_value = session_json

        store = RedisSessionStore(mock_redis)
        store.load("abc-123")

        mock_redis.get.assert_called_once_with("session:abc-123")


class TestRedisSessionStoreDelete:
    """Testes para método delete."""

    def test_delete_session_success(self):
        """Deve deletar sessão com sucesso."""
        mock_redis = MagicMock()
        mock_redis.delete.return_value = 1

        store = RedisSessionStore(mock_redis)
        result = store.delete("test-session-123")

        assert result is True
        mock_redis.delete.assert_called_once_with("session:test-session-123")

    def test_delete_session_not_found(self):
        """Deve retornar False se sessão não existe."""
        mock_redis = MagicMock()
        mock_redis.delete.return_value = 0

        store = RedisSessionStore(mock_redis)
        result = store.delete("nonexistent-session")

        assert result is False

    def test_delete_session_redis_error(self):
        """Deve retornar False e fazer log se Redis falhar."""
        mock_redis = MagicMock()
        mock_redis.delete.side_effect = Exception("Redis error")

        store = RedisSessionStore(mock_redis)
        result = store.delete("test-session")

        assert result is False


class TestRedisSessionStoreExists:
    """Testes para método exists."""

    def test_exists_session_true(self):
        """Deve retornar True para sessão existente."""
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 1

        store = RedisSessionStore(mock_redis)
        result = store.exists("test-session-123")

        assert result is True
        mock_redis.exists.assert_called_once_with("session:test-session-123")

    def test_exists_session_false(self):
        """Deve retornar False para sessão inexistente."""
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 0

        store = RedisSessionStore(mock_redis)
        result = store.exists("nonexistent-session")

        assert result is False

    def test_exists_session_redis_error(self):
        """Deve retornar False e fazer log se Redis falhar."""
        mock_redis = MagicMock()
        mock_redis.exists.side_effect = Exception("Redis error")

        store = RedisSessionStore(mock_redis)
        result = store.exists("test-session")

        assert result is False

    def test_exists_session_key_format(self):
        """Deve verificar com formato correto de chave."""
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 1

        store = RedisSessionStore(mock_redis)
        store.exists("abc-123-xyz")

        mock_redis.exists.assert_called_once_with("session:abc-123-xyz")


class TestRedisSessionStoreIntegration:
    """Testes de integração com Redis."""

    def _create_session_json(self, session_id: str = "test-session") -> str:
        """Helper para criar JSON de sessão."""
        session = SessionState(
            session_id=session_id,
            lead_profile=LeadProfile(phone="+5511987654321", name="Test User"),
            intent_queue=IntentQueue(),
            outcome=Outcome.AWAITING_USER,
        )
        return session.model_dump_json()

    def test_save_load_cycle(self):
        """Deve salvar e carregar sessão com sucesso."""
        stored_data = {}

        def mock_setex(key, ttl, value):
            stored_data[key] = value

        def mock_get(key):
            return stored_data.get(key)

        mock_redis = MagicMock()
        mock_redis.setex = mock_setex
        mock_redis.get = mock_get

        store = RedisSessionStore(mock_redis)

        # Salvar
        session = SessionState(
            session_id="test-session",
            lead_profile=LeadProfile(phone="+5511987654321", name="Test User"),
            intent_queue=IntentQueue(),
            outcome=Outcome.AWAITING_USER,
        )
        store.save(session, ttl_seconds=3600)

        # Carregar
        loaded = store.load("test-session")
        assert loaded is not None
        assert loaded.session_id == "test-session"
        assert loaded.lead_profile.phone == "+5511987654321"

    def test_delete_after_save(self):
        """Deve deletar sessão após salvar."""
        stored_data = {}

        def mock_setex(key, ttl, value):
            stored_data[key] = value

        def mock_get(key):
            return stored_data.get(key)

        def mock_delete(key):
            return 1 if key in stored_data else 0

        mock_redis = MagicMock()
        mock_redis.setex = mock_setex
        mock_redis.get = mock_get
        mock_redis.delete = mock_delete

        store = RedisSessionStore(mock_redis)

        # Salvar
        session = SessionState(
            session_id="test-session",
            lead_profile=LeadProfile(phone="+5511987654321", name="Test User"),
            intent_queue=IntentQueue(),
            outcome=Outcome.AWAITING_USER,
        )
        store.save(session)

        # Verificar que existe
        mock_redis.exists = lambda k: 1 if k in stored_data else 0
        assert store.exists("test-session") is True

        # Deletar
        result = store.delete("test-session")
        assert result is True
