"""Testes para SessionStore em memória."""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest

from pyloto_corp.application.session import SessionState
from pyloto_corp.domain.models import LeadProfile
from pyloto_corp.domain.intent_queue import IntentQueue
from pyloto_corp.infra.session_store_memory import InMemorySessionStore


class TestInMemorySessionStoreSave:
    """Testes para método save."""

    def _create_mock_session(self, session_id: str = "test-session-123") -> SessionState:
        """Cria uma sessão de teste válida."""
        return SessionState(
            session_id=session_id,
            lead_profile=LeadProfile(phone="+5511987654321", name="Test User"),
            intent_queue=IntentQueue(),
        )

    def test_save_session_success(self):
        """Deve salvar sessão em memória."""
        store = InMemorySessionStore()
        session = self._create_mock_session()

        store.save(session, ttl_seconds=3600)

        assert "test-session-123" in store._sessions
        saved_session, expire_at = store._sessions["test-session-123"]
        assert saved_session.session_id == "test-session-123"

    def test_save_session_sets_expiration(self):
        """Deve definir tempo de expiração correto."""
        store = InMemorySessionStore()
        session = self._create_mock_session()
        before_save = datetime.now(tz=UTC).timestamp()

        store.save(session, ttl_seconds=60)

        after_save = datetime.now(tz=UTC).timestamp()
        _, expire_at = store._sessions["test-session-123"]

        # A expiração deve estar entre 60 e 61 segundos no futuro
        time_until_expiry = expire_at - before_save
        assert 59 < time_until_expiry < 62

    def test_save_session_default_ttl(self):
        """Deve usar TTL padrão (7200 segundos)."""
        store = InMemorySessionStore()
        session = self._create_mock_session()
        before_save = datetime.now(tz=UTC).timestamp()

        store.save(session)

        _, expire_at = store._sessions["test-session-123"]
        time_until_expiry = expire_at - before_save

        # TTL padrão é 7200 segundos
        assert 7199 < time_until_expiry < 7201

    def test_save_overwrites_existing_session(self):
        """Deve sobrescrever sessão existente."""
        store = InMemorySessionStore()
        session1 = self._create_mock_session(session_id="same-id")
        session2 = self._create_mock_session(session_id="same-id")

        store.save(session1)
        store.save(session2)

        assert len(store._sessions) == 1
        saved_session, _ = store._sessions["same-id"]
        assert saved_session == session2


class TestInMemorySessionStoreLoad:
    """Testes para método load."""

    def _create_session(self, session_id: str = "test-session") -> SessionState:
        """Helper para criar sessão."""
        return SessionState(
            session_id=session_id,
            lead_profile=LeadProfile(phone="+5511987654321", name="Test User"),
            intent_queue=IntentQueue(),
        )

    def test_load_session_success(self):
        """Deve carregar sessão válida."""
        store = InMemorySessionStore()
        session = self._create_session()
        store.save(session, ttl_seconds=3600)

        loaded = store.load("test-session")

        assert loaded is not None
        assert loaded.session_id == "test-session"
        assert loaded.lead_profile.phone == "+5511987654321"

    def test_load_session_not_found(self):
        """Deve retornar None para sessão inexistente."""
        store = InMemorySessionStore()

        loaded = store.load("nonexistent")

        assert loaded is None

    def test_load_session_expired(self):
        """Deve deletar e retornar None para sessão expirada."""
        store = InMemorySessionStore()
        session = self._create_session()

        # Salvar com TTL muito curto (0.1 segundos)
        store.save(session, ttl_seconds=1)

        # Aguardar expiração
        time.sleep(1.1)

        loaded = store.load("test-session")

        assert loaded is None
        # Sessão deve ter sido deletada
        assert "test-session" not in store._sessions

    def test_load_returns_same_object(self):
        """Deve retornar a mesma instância de sessão."""
        store = InMemorySessionStore()
        session = self._create_session()
        store.save(session)

        loaded = store.load("test-session")

        # Deve ser a mesma instância
        assert loaded is session

    def test_load_multiple_sessions(self):
        """Deve carregar sessões diferentes."""
        store = InMemorySessionStore()
        session1 = self._create_session(session_id="session-1")
        session2 = self._create_session(session_id="session-2")

        store.save(session1)
        store.save(session2)

        loaded1 = store.load("session-1")
        loaded2 = store.load("session-2")

        assert loaded1.session_id == "session-1"
        assert loaded2.session_id == "session-2"


class TestInMemorySessionStoreDelete:
    """Testes para método delete."""

    def _create_session(self, session_id: str = "test-session") -> SessionState:
        """Helper para criar sessão."""
        return SessionState(
            session_id=session_id,
            lead_profile=LeadProfile(phone="+5511987654321", name="Test User"),
            intent_queue=IntentQueue(),
        )

    def test_delete_session_success(self):
        """Deve deletar sessão com sucesso."""
        store = InMemorySessionStore()
        session = self._create_session()
        store.save(session)

        result = store.delete("test-session")

        assert result is True
        assert "test-session" not in store._sessions

    def test_delete_session_not_found(self):
        """Deve retornar False para sessão inexistente."""
        store = InMemorySessionStore()

        result = store.delete("nonexistent")

        assert result is False

    def test_delete_nonexistent_does_not_fail(self):
        """Deletar sessão inexistente não deve lançar exceção."""
        store = InMemorySessionStore()

        # Não deve lançar exceção
        result = store.delete("nonexistent")
        assert result is False


class TestInMemorySessionStoreExists:
    """Testes para método exists."""

    def _create_session(self, session_id: str = "test-session") -> SessionState:
        """Helper para criar sessão."""
        return SessionState(
            session_id=session_id,
            lead_profile=LeadProfile(phone="+5511987654321", name="Test User"),
            intent_queue=IntentQueue(),
        )

    def test_exists_true_for_valid_session(self):
        """Deve retornar True para sessão válida."""
        store = InMemorySessionStore()
        session = self._create_session()
        store.save(session, ttl_seconds=3600)

        result = store.exists("test-session")

        assert result is True

    def test_exists_false_for_nonexistent(self):
        """Deve retornar False para sessão inexistente."""
        store = InMemorySessionStore()

        result = store.exists("nonexistent")

        assert result is False

    def test_exists_false_for_expired(self):
        """Deve retornar False para sessão expirada."""
        store = InMemorySessionStore()
        session = self._create_session()
        store.save(session, ttl_seconds=1)

        time.sleep(1.1)

        result = store.exists("test-session")

        assert result is False

    def test_exists_does_not_remove_valid_session(self):
        """Conferir existência não deve remover sessão válida."""
        store = InMemorySessionStore()
        session = self._create_session()
        store.save(session, ttl_seconds=3600)

        result = store.exists("test-session")

        assert result is True
        # Sessão ainda deve estar lá
        loaded = store.load("test-session")
        assert loaded is not None


class TestInMemorySessionStoreIntegration:
    """Testes de integração."""

    def _create_session(self, session_id: str = "test-session") -> SessionState:
        """Helper para criar sessão."""
        return SessionState(
            session_id=session_id,
            lead_profile=LeadProfile(phone="+5511987654321", name="Test User"),
            intent_queue=IntentQueue(),
        )

    def test_save_load_delete_cycle(self):
        """Deve realizar ciclo completo save-load-delete."""
        store = InMemorySessionStore()
        session = self._create_session()

        # Salvar
        store.save(session)
        assert store.exists("test-session")

        # Carregar
        loaded = store.load("test-session")
        assert loaded.session_id == "test-session"

        # Deletar
        result = store.delete("test-session")
        assert result is True
        assert not store.exists("test-session")

    def test_multiple_sessions_independent(self):
        """Sessões múltiplas devem ser independentes."""
        store = InMemorySessionStore()
        session1 = self._create_session(session_id="session-1")
        session2 = self._create_session(session_id="session-2")

        store.save(session1, ttl_seconds=1)
        store.save(session2, ttl_seconds=3600)

        # Aguardar expiração de session1
        time.sleep(1.1)

        # session1 deve estar expirada
        assert store.load("session-1") is None

        # session2 deve estar válida
        assert store.load("session-2") is not None

    def test_empty_store_operations(self):
        """Operações em store vazio devem ser seguras."""
        store = InMemorySessionStore()

        assert store.load("any") is None
        assert store.exists("any") is False
        assert store.delete("any") is False
        assert len(store._sessions) == 0

    def test_isolated_instances(self):
        """Instâncias diferentes devem ter stores isolados."""
        store1 = InMemorySessionStore()
        store2 = InMemorySessionStore()

        session = self._create_session()
        store1.save(session)

        # store2 não deve ter a sessão
        assert store2.load("test-session") is None
