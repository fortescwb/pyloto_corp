"""Firestore implementation of AuditLogStore."""

from __future__ import annotations

from google.cloud import firestore

from pyloto_corp.domain.audit import AuditEvent, AuditLogStore


class FirestoreAuditLogStore(AuditLogStore):
    def __init__(self, client: firestore.Client, collection: str = "conversations") -> None:
        self._client = client
        self._collection = collection

    def _audit_collection(self, user_key: str) -> firestore.CollectionReference:
        return (
            self._client.collection(self._collection)
            .document(user_key)
            .collection("audit")
        )

    def get_latest_event(self, user_key: str) -> AuditEvent | None:
        query = (
            self._audit_collection(user_key)
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(1)
        )
        docs = list(query.stream())
        if not docs:
            return None
        return AuditEvent(**(docs[0].to_dict() or {}))

    def list_events(self, user_key: str, limit: int = 500) -> list[AuditEvent]:
        query = (
            self._audit_collection(user_key)
            .order_by("timestamp", direction=firestore.Query.ASCENDING)
            .limit(limit)
        )
        return [AuditEvent(**(doc.to_dict() or {})) for doc in query.stream()]

    def append_event(self, event: AuditEvent, expected_prev_hash: str | None) -> bool:
        audit_col = self._audit_collection(event.user_key)
        doc_ref = audit_col.document(event.event_id)
        transaction = self._client.transaction()

        @firestore.transactional
        def _txn(tx: firestore.Transaction) -> bool:
            # valida cadeia
            latest_docs = list(
                audit_col.order_by("timestamp", direction=firestore.Query.DESCENDING)
                .limit(1)
                .stream(transaction=tx)
            )
            latest_hash = None
            if latest_docs:
                latest_hash = (latest_docs[0].to_dict() or {}).get("hash")

            if latest_hash != expected_prev_hash:
                return False

            tx.create(doc_ref, event.model_dump())
            return True

        return _txn(transaction)
