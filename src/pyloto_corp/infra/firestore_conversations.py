"""Implementação Firestore do ConversationStore."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore

from pyloto_corp.domain.conversations import (
    AppendResult,
    ConversationHeader,
    ConversationMessage,
    ConversationStore,
    Page,
)


class FirestoreConversationStore(ConversationStore):
    """Store de conversas usando Firestore.

    Coleção escolhida: conversations/{user_key}
    O tenant_id, quando existir, fica no documento do header.
    """

    def __init__(
        self, client: firestore.Client, collection: str = "conversations"
    ) -> None:
        self._client = client
        self._collection = collection

    def _header_ref(self, user_key: str) -> firestore.DocumentReference:
        return self._client.collection(self._collection).document(user_key)

    def _message_ref(
        self, user_key: str, provider_message_id: str
    ) -> firestore.DocumentReference:
        return (
            self._client.collection(self._collection)
            .document(user_key)
            .collection("messages")
            .document(provider_message_id)
        )

    def append_message(self, message: ConversationMessage) -> AppendResult:
        header_ref = self._header_ref(message.user_key)
        message_ref = self._message_ref(
            message.user_key, message.provider_message_id
        )
        now = datetime.now(tz=UTC)

        @firestore.transactional
        def _txn(transaction: firestore.Transaction) -> AppendResult:
            snapshot = message_ref.get(transaction=transaction)
            if snapshot.exists:
                return AppendResult(created=False)

            transaction.create(message_ref, message.model_dump())

            header_snapshot = header_ref.get(transaction=transaction)
            if header_snapshot.exists:
                data = header_snapshot.to_dict() or {}
                last_message_at = data.get(
                    "last_message_at", message.timestamp
                )
                if isinstance(last_message_at, datetime):
                    last_message_at = max(last_message_at, message.timestamp)
                else:
                    last_message_at = message.timestamp

                header_update = {
                    "channel": "whatsapp",
                    "tenant_id": message.tenant_id,
                    "updated_at": now,
                    "last_message_at": last_message_at,
                }
                transaction.set(header_ref, header_update, merge=True)
            else:
                header = ConversationHeader(
                    user_key=message.user_key,
                    channel="whatsapp",
                    tenant_id=message.tenant_id,
                    created_at=now,
                    updated_at=now,
                    last_message_at=message.timestamp,
                )
                transaction.create(header_ref, header.model_dump())

            return AppendResult(created=True)

        try:
            return _txn(self._client.transaction())
        except AlreadyExists:
            return AppendResult(created=False)

    def get_messages(
        self, user_key: str, limit: int, cursor: str | None = None
    ) -> Page:
        messages_ref = (
            self._client.collection(self._collection)
            .document(user_key)
            .collection("messages")
        )
        query = messages_ref.order_by(
            "timestamp", direction=firestore.Query.DESCENDING
        ).limit(limit)

        if cursor:
            cursor_ref = messages_ref.document(cursor)
            cursor_snapshot = cursor_ref.get()
            if cursor_snapshot.exists:
                query = query.start_after(cursor_snapshot)

        docs = list(query.stream())
        items = [
            ConversationMessage(**(doc.to_dict() or {})) for doc in docs
        ]
        next_cursor = docs[-1].id if len(docs) == limit else None

        return Page(items=items, next_cursor=next_cursor)

    def get_header(self, user_key: str) -> ConversationHeader | None:
        snapshot = self._header_ref(user_key).get()
        if not snapshot.exists:
            return None
        data: dict[str, Any] = snapshot.to_dict() or {}
        return ConversationHeader(**data)
