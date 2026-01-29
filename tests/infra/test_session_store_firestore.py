"""Testes para SessionStore baseado em Firestore."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from pyloto_corp.application.session import SessionState
from pyloto_corp.domain.enums import Outcome
from pyloto_corp.domain.intent_queue import IntentQueue
from pyloto_corp.domain.models import LeadProfile
from pyloto_corp.infra.session_contract import SessionStoreError
from pyloto_corp.infra.session_store_firestore import FirestoreSessionStore, _parse_expire_at


class TestParseExpireAt:
    """Testes para função _parse_expire_at."""

    def test_parse_expire_at_none(self):
        """Deve retornar None para entrada None."""
        result = _parse_expire_at(None)
        assert result is None

    def test_parse_expire_at_datetime(self):
        """Deve retornar datetime se já for datetime."""
        now = datetime.now(tz=UTC)
        result = _parse_expire_at(now)
        assert result == now

    def test_parse_expire_at_iso_string_with_z(self):
        """Deve converter string ISO com Z para datetime."""
        iso_str = "2026-01-26T10:30:00Z"
        result = _parse_expire_at(iso_str)
        assert result is not None
        assert isinstance(result, datetime)

    def test_parse_expire_at_iso_string_with_offset(self):
        """Deve converter string ISO com offset."""
        iso_str = "2026-01-26T10:30:00+00:00"
        result = _parse_expire_at(iso_str)
        assert result is not None
        assert isinstance(result, datetime)

    def test_parse_expire_at_invalid_string(self):
        """Deve retornar None para string inválida."""
        result = _parse_expire_at("invalid-date")
        assert result is None


class TestFirestoreSessionStoreSave:
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
        """Deve salvar sessão com TTL no Firestore."""
        mock_client = MagicMock()
        mock_doc_ref = MagicMock()
        mock_client.collection.return_value.document.return_value = mock_doc_ref

        store = FirestoreSessionStore(mock_client, collection="sessions")
        session = self._create_mock_session()

        store.save(session, ttl_seconds=3600)

        mock_client.collection.assert_called_once_with("sessions")
        mock_client.collection.return_value.document.assert_called_once_with("test-session-123")
        mock_doc_ref.set.assert_called_once()

        # Verificar que _ttl_expire_at foi adicionado ao payload
        call_args = mock_doc_ref.set.call_args
        payload = call_args[0][0]
        assert "_ttl_expire_at" in payload
        assert isinstance(payload["_ttl_expire_at"], datetime)

    def test_save_session_default_ttl(self):
        """Deve usar TTL padrão (7200 segundos) se não especificado."""
        mock_client = MagicMock()
        mock_doc_ref = MagicMock()
        mock_client.collection.return_value.document.return_value = mock_doc_ref

        store = FirestoreSessionStore(mock_client)
        session = self._create_mock_session()

        store.save(session)

        call_args = mock_doc_ref.set.call_args
        payload = call_args[0][0]
        assert "_ttl_expire_at" in payload

    def test_save_session_firestore_error(self):
        """Deve lançar SessionStoreError se Firestore falhar."""
        mock_client = MagicMock()
        mock_doc_ref = MagicMock()
        mock_doc_ref.set.side_effect = Exception("Firestore connection failed")
        mock_client.collection.return_value.document.return_value = mock_doc_ref

        store = FirestoreSessionStore(mock_client)
        session = self._create_mock_session()

        with pytest.raises(SessionStoreError):
            store.save(session)


class TestFirestoreSessionStoreLoad:
    """Testes para método load."""

    def _create_mock_session_data(self) -> dict:
        """Cria dados de sessão de teste para mock."""
        return {
            "session_id": "test-session-123",
            "created_at": (datetime.now(tz=UTC) - timedelta(hours=1)).isoformat(),
            "updated_at": datetime.now(tz=UTC).isoformat(),
            "lead_profile": {
                "phone": "+5511987654321",
                "name": "Test User",
                "city": None,
                "is_business": None,
                "business_name": None,
                "role": None,
            },
            "intent_queue": {
                "items": [],
                "active_index": None,
            },
            "outcome": Outcome.AWAITING_USER.value,
            "_ttl_expire_at": datetime.now(tz=UTC) + timedelta(hours=1),
        }

    def test_load_session_success(self):
        """Deve carregar sessão válida do Firestore."""
        mock_client = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = self._create_mock_session_data()
        mock_client.collection.return_value.document.return_value.get.return_value = mock_doc

        store = FirestoreSessionStore(mock_client)
        result = store.load("test-session-123")

        assert result is not None
        assert result.session_id == "test-session-123"
        assert result.lead_profile.phone == "+5511987654321"

    def test_load_session_not_found(self):
        """Deve retornar None se sessão não existe."""
        mock_client = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_client.collection.return_value.document.return_value.get.return_value = mock_doc

        store = FirestoreSessionStore(mock_client)
        result = store.load("nonexistent-session")

        assert result is None

    def test_load_session_expired(self):
        """Deve deletar e retornar None para sessão expirada."""
        mock_client = MagicMock()
        mock_doc = MagicMock()
        mock_doc_ref = MagicMock()
        mock_doc.exists = True
        expired_data = self._create_mock_session_data()
        expired_data["_ttl_expire_at"] = datetime.now(tz=UTC) - timedelta(hours=1)
        mock_doc.to_dict.return_value = expired_data
        mock_client.collection.return_value.document.return_value = mock_doc_ref
        mock_doc_ref.get.return_value = mock_doc

        store = FirestoreSessionStore(mock_client)
        result = store.load("expired-session")

        assert result is None
        mock_doc_ref.delete.assert_called_once()

    def test_load_session_firestore_error(self):
        """Deve retornar None e fazer log se Firestore falhar."""
        mock_client = MagicMock()
        mock_client.collection.return_value.document.return_value.get.side_effect = Exception(
            "Firestore error"
        )

        store = FirestoreSessionStore(mock_client)
        result = store.load("test-session")

        assert result is None

    def test_load_session_without_ttl(self):
        """Deve carregar sessão sem _ttl_expire_at (compatibilidade)."""
        mock_client = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        data = self._create_mock_session_data()
        del data["_ttl_expire_at"]
        mock_doc.to_dict.return_value = data
        mock_client.collection.return_value.document.return_value.get.return_value = mock_doc

        store = FirestoreSessionStore(mock_client)
        result = store.load("test-session")

        assert result is not None
        assert result.session_id == "test-session-123"


class TestFirestoreSessionStoreDelete:
    """Testes para método delete."""

    def test_delete_session_success(self):
        """Deve deletar sessão com sucesso."""
        mock_client = MagicMock()
        mock_doc_ref = MagicMock()
        mock_client.collection.return_value.document.return_value = mock_doc_ref

        store = FirestoreSessionStore(mock_client)
        result = store.delete("test-session-123")

        assert result is True
        mock_doc_ref.delete.assert_called_once()

    def test_delete_session_firestore_error(self):
        """Deve retornar False e fazer log se Firestore falhar."""
        mock_client = MagicMock()
        mock_doc_ref = MagicMock()
        mock_doc_ref.delete.side_effect = Exception("Firestore error")
        mock_client.collection.return_value.document.return_value = mock_doc_ref

        store = FirestoreSessionStore(mock_client)
        result = store.delete("test-session")

        assert result is False


class TestFirestoreSessionStoreExists:
    """Testes para método exists."""

    def _create_valid_session_data(self) -> dict:
        """Cria dados válidos de sessão."""
        return {
            "session_id": "test-session",
            "user": {
                "phone_number": "+5511987654321",
                "name": "Test User",
            },
            "active_intent": None,
            "intents": [],
            "context": {},
            "_ttl_expire_at": datetime.now(tz=UTC) + timedelta(hours=1),
        }

    def test_exists_session_true(self):
        """Deve retornar True para sessão válida existente."""
        mock_client = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = self._create_valid_session_data()
        mock_client.collection.return_value.document.return_value.get.return_value = mock_doc

        store = FirestoreSessionStore(mock_client)
        result = store.exists("test-session")

        assert result is True

    def test_exists_session_false_not_found(self):
        """Deve retornar False se sessão não existe."""
        mock_client = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_client.collection.return_value.document.return_value.get.return_value = mock_doc

        store = FirestoreSessionStore(mock_client)
        result = store.exists("nonexistent-session")

        assert result is False

    def test_exists_session_false_expired(self):
        """Deve retornar False para sessão expirada."""
        mock_client = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        expired_data = self._create_valid_session_data()
        expired_data["_ttl_expire_at"] = datetime.now(tz=UTC) - timedelta(hours=1)
        mock_doc.to_dict.return_value = expired_data
        mock_client.collection.return_value.document.return_value.get.return_value = mock_doc

        store = FirestoreSessionStore(mock_client)
        result = store.exists("expired-session")

        assert result is False

    def test_exists_session_firestore_error(self):
        """Deve retornar False e fazer log se Firestore falhar."""
        mock_client = MagicMock()
        mock_client.collection.return_value.document.return_value.get.side_effect = Exception(
            "Firestore error"
        )

        store = FirestoreSessionStore(mock_client)
        result = store.exists("test-session")

        assert result is False


class TestFirestoreSessionStoreIntegration:
    """Testes de integração com Firestore."""

    def _create_session(self, session_id: str = "test-session") -> SessionState:
        """Helper para criar sessão."""
        return SessionState(
            session_id=session_id,
            lead_profile=LeadProfile(phone="+5511987654321", name="Test User"),
            intent_queue=IntentQueue(),
            outcome=Outcome.AWAITING_USER,
        )

    def test_save_load_cycle(self):
        """Deve salvar e carregar sessão com sucesso."""
        mock_client = MagicMock()
        session_data = None

        def mock_set(data):
            nonlocal session_data
            session_data = data

        mock_doc_ref = MagicMock()
        mock_doc_ref.set = mock_set
        mock_client.collection.return_value.document.return_value = mock_doc_ref

        store = FirestoreSessionStore(mock_client)
        session = self._create_session()
        store.save(session, ttl_seconds=3600)

        # Agora simular carregamento
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = session_data
        mock_client.collection.return_value.document.return_value.get.return_value = mock_doc

        loaded = store.load("test-session")
        assert loaded is not None
        assert loaded.session_id == "test-session"
        assert loaded.lead_profile.phone == "+5511987654321"

    def test_custom_collection_name(self):
        """Deve usar nome de coleção customizado."""
        mock_client = MagicMock()
        mock_doc_ref = MagicMock()
        mock_client.collection.return_value.document.return_value = mock_doc_ref

        store = FirestoreSessionStore(mock_client, collection="custom_sessions")
        session = self._create_session()
        store.save(session)

        mock_client.collection.assert_called_with("custom_sessions")
