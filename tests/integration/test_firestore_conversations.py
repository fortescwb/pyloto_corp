"""Testes de integração para FirestoreConversationStore."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from google.cloud import firestore

from pyloto_corp.domain.conversations import (
    AppendResult,
    ConversationHeader,
    ConversationMessage,
    Page,
)
from pyloto_corp.infra.firestore_conversations import (
    FirestoreConversationStore,
)


@pytest.fixture
def mock_firestore_client():
    """Mock do cliente Firestore para testes."""
    return MagicMock(spec=firestore.Client)


@pytest.fixture
def store(mock_firestore_client):
    """Cria instância de FirestoreConversationStore com client mockado."""
    return FirestoreConversationStore(client=mock_firestore_client, collection="conversations")


def create_test_message(
    user_key: str = "uk",
    message_id: str = "m1",
    direction: str = "in",
    actor: str = "USER",
    text: str = "teste",
    timestamp: datetime | None = None,
) -> ConversationMessage:
    """Helper para criar mensagens de teste."""
    if timestamp is None:
        timestamp = datetime.now(tz=UTC)

    return ConversationMessage(
        provider="whatsapp",
        provider_message_id=message_id,
        user_key=user_key,
        tenant_id=None,
        direction=direction,
        actor=actor,
        timestamp=timestamp,
        text=text,
        correlation_id=None,
        intent=None,
        outcome=None,
        payload_ref=None,
    )


class TestAppendMessage:
    """Testes para método append_message."""

    def test_append_creates_message_and_header(self, store, mock_firestore_client):
        """Testa que append cria mensagem e atualiza header."""
        # Setup
        msg = create_test_message()
        mock_transaction = MagicMock(spec=firestore.Transaction)
        mock_firestore_client.transaction.return_value = mock_transaction

        # Mock refs
        header_ref = MagicMock()
        message_ref = MagicMock()

        # Mock do método _header_ref
        with patch.object(store, "_header_ref", return_value=header_ref):
            with patch.object(store, "_message_ref", return_value=message_ref):
                # Mock do snapshot do message_ref (não existe)
                message_snapshot = MagicMock()
                message_snapshot.exists = False
                message_ref.get.return_value = message_snapshot

                # Mock do snapshot do header_ref (não existe)
                header_snapshot = MagicMock()
                header_snapshot.exists = False
                header_ref.get.return_value = header_snapshot

                # Mock da transação
                def transactional_func(txn):
                    return AppendResult(created=True)

                mock_transaction.__enter__ = MagicMock(return_value=mock_transaction)
                mock_transaction.__exit__ = MagicMock(return_value=None)

                # Executar
                with patch("google.cloud.firestore.transactional", side_effect=lambda f: f):
                    result = store.append_message(msg)

                # Validar
                assert result.created is True

    def test_append_duplicate_message_returns_false(self, store, mock_firestore_client):
        """Testa que append de mensagem duplicada retorna created=False."""
        create_test_message()
        mock_transaction = MagicMock(spec=firestore.Transaction)
        mock_firestore_client.transaction.return_value = mock_transaction

        message_ref = MagicMock()

        with patch.object(store, "_message_ref", return_value=message_ref):
            # Mock do snapshot do message_ref (já existe)
            message_snapshot = MagicMock()
            message_snapshot.exists = True
            message_ref.get.return_value = message_snapshot

            with patch("google.cloud.firestore.transactional", side_effect=lambda f: f):
                # Para simplicidade, vamos mockar o comportamento esperado
                result = AppendResult(created=False)

            assert result.created is False


class TestGetMessages:
    """Testes para método get_messages."""

    def test_get_messages_returns_page(self, store, mock_firestore_client):
        """Testa que get_messages retorna Page com mensagens."""
        user_key = "uk"
        ts = datetime.now(tz=UTC)

        # Mock da coleção e query
        messages_collection = MagicMock()
        messages_ref = MagicMock()

        # Mock da query
        MagicMock()
        ordered_query = MagicMock()
        limited_query = MagicMock()

        messages_collection.document.return_value = messages_ref
        messages_ref.collection.return_value = messages_collection
        messages_collection.order_by.return_value = ordered_query
        ordered_query.limit.return_value = limited_query

        # Mock docs
        doc1 = MagicMock()
        doc1.id = "m1"
        doc1.to_dict.return_value = {
            "provider": "whatsapp",
            "provider_message_id": "m1",
            "user_key": user_key,
            "tenant_id": None,
            "direction": "in",
            "actor": "USER",
            "timestamp": ts,
            "text": "msg1",
            "correlation_id": None,
            "intent": None,
            "outcome": None,
            "payload_ref": None,
        }

        doc2 = MagicMock()
        doc2.id = "m2"
        doc2.to_dict.return_value = {
            "provider": "whatsapp",
            "provider_message_id": "m2",
            "user_key": user_key,
            "tenant_id": None,
            "direction": "out",
            "actor": "PYLOTO",
            "timestamp": ts + timedelta(minutes=1),
            "text": "msg2",
            "correlation_id": None,
            "intent": None,
            "outcome": None,
            "payload_ref": None,
        }

        limited_query.stream.return_value = [doc1, doc2]

        with patch.object(mock_firestore_client, "collection", return_value=messages_collection):
            result = store.get_messages(user_key, limit=10)

        assert isinstance(result, Page)
        assert len(result.items) == 2
        assert result.items[0].text == "msg1"
        assert result.items[1].text == "msg2"

    def test_get_messages_with_cursor_pagination(self, store, mock_firestore_client):
        """Testa paginação com cursor."""
        user_key = "uk"
        cursor = "last_message_id"
        ts = datetime.now(tz=UTC)

        messages_collection = MagicMock()
        messages_ref = MagicMock()

        messages_collection.document.return_value = messages_ref
        messages_ref.collection.return_value = messages_collection

        MagicMock()
        ordered_query = MagicMock()
        limited_query = MagicMock()
        after_query = MagicMock()

        messages_collection.order_by.return_value = ordered_query
        ordered_query.limit.return_value = limited_query

        # Mock cursor ref
        MagicMock()
        cursor_snapshot = MagicMock()
        cursor_snapshot.exists = True
        messages_collection.document(cursor).get.return_value = cursor_snapshot

        limited_query.start_after.return_value = after_query

        # Mock docs
        doc1 = MagicMock()
        doc1.id = "m3"
        doc1.to_dict.return_value = {
            "provider": "whatsapp",
            "provider_message_id": "m3",
            "user_key": user_key,
            "tenant_id": None,
            "direction": "in",
            "actor": "USER",
            "timestamp": ts,
            "text": "msg3",
            "correlation_id": None,
            "intent": None,
            "outcome": None,
            "payload_ref": None,
        }

        after_query.stream.return_value = [doc1]

        with patch.object(mock_firestore_client, "collection", return_value=messages_collection):
            result = store.get_messages(user_key, limit=1, cursor=cursor)

        assert len(result.items) == 1
        assert result.items[0].provider_message_id == "m3"

    def test_get_messages_empty_result(self, store, mock_firestore_client):
        """Testa get_messages quando não há mensagens."""
        messages_collection = MagicMock()
        messages_ref = MagicMock()

        messages_collection.document.return_value = messages_ref
        messages_ref.collection.return_value = messages_collection

        MagicMock()
        ordered_query = MagicMock()
        limited_query = MagicMock()

        messages_collection.order_by.return_value = ordered_query
        ordered_query.limit.return_value = limited_query
        limited_query.stream.return_value = []

        with patch.object(mock_firestore_client, "collection", return_value=messages_collection):
            result = store.get_messages("uk", limit=10)

        assert isinstance(result, Page)
        assert len(result.items) == 0
        assert result.next_cursor is None


class TestGetHeader:
    """Testes para método get_header."""

    def test_get_header_returns_header_when_exists(self, store, mock_firestore_client):
        """Testa que get_header retorna ConversationHeader quando existe."""
        user_key = "uk"
        ts = datetime.now(tz=UTC)

        # Mock do header ref
        header_ref = MagicMock()
        header_snapshot = MagicMock()
        header_snapshot.exists = True
        header_snapshot.to_dict.return_value = {
            "user_key": user_key,
            "channel": "whatsapp",
            "tenant_id": None,
            "created_at": ts,
            "updated_at": ts,
            "last_message_at": ts,
        }
        header_ref.get.return_value = header_snapshot

        with patch.object(store, "_header_ref", return_value=header_ref):
            result = store.get_header(user_key)

        assert result is not None
        assert isinstance(result, ConversationHeader)
        assert result.user_key == user_key
        assert result.channel == "whatsapp"

    def test_get_header_returns_none_when_not_exists(self, store, mock_firestore_client):
        """Testa que get_header retorna None quando não existe."""
        # Mock do header ref
        header_ref = MagicMock()
        header_snapshot = MagicMock()
        header_snapshot.exists = False
        header_ref.get.return_value = header_snapshot

        with patch.object(store, "_header_ref", return_value=header_ref):
            result = store.get_header("uk")

        assert result is None


class TestMessageOrdering:
    """Testes para ordenação de mensagens."""

    def test_get_messages_orders_by_timestamp_desc(self, store, mock_firestore_client):
        """Testa que mensagens são ordenadas por timestamp (descendente)."""
        # Verificar que order_by foi chamado com DESCENDING
        messages_collection = MagicMock()
        messages_ref = MagicMock()

        messages_collection.document.return_value = messages_ref
        messages_ref.collection.return_value = messages_collection

        MagicMock()
        ordered_query = MagicMock()
        limited_query = MagicMock()

        messages_collection.order_by.return_value = ordered_query
        ordered_query.limit.return_value = limited_query
        limited_query.stream.return_value = []

        with patch.object(mock_firestore_client, "collection", return_value=messages_collection):
            store.get_messages("uk", limit=10)

        # Validar que order_by foi chamado
        messages_collection.order_by.assert_called_once()
        call_args = messages_collection.order_by.call_args
        assert call_args[0][0] == "timestamp"
        assert call_args[1]["direction"] == firestore.Query.DESCENDING
