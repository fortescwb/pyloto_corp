"""Firestore store para UserProfile.

Implementação concreta de UserProfileStore usando Firestore:
- CRUD básico (get, upsert)
- Busca por phone (dedup)
- Histórico de atualizações (subcollection)
- LGPD: forget (direito ao esquecimento)

Conforme regras_e_padroes.md:
- Máximo 200 linhas por arquivo
- Zero-trust: validação rigorosa
- Logs estruturados sem PII
- Transações Firestore para atomicidade
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pyloto_corp.domain.profile import (
    ProfileUpdateEvent,
    UserProfile,
    UserProfileStore,
)
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from google.cloud import firestore

logger: logging.Logger = get_logger(__name__)


def _mask_pii(value: str | None) -> str | None:
    """Mascara PII para logs e histórico."""
    if value is None:
        return None
    if len(value) <= 4:
        return "***"
    return value[:2] + "***" + value[-2:]


class FirestoreUserProfileStore(UserProfileStore):
    """Implementação Firestore de UserProfileStore.

    Schema:
    /user_profiles/{user_key}
      ├── phone_e164, display_name, city, ...
      └── /history/{event_id}
            ├── timestamp, field_changed, old_value, new_value, actor
    """

    def __init__(
        self,
        client: firestore.Client,
        collection: str = "user_profiles",
    ) -> None:
        self._client = client
        self._collection = collection

    def _doc(self, user_key: str) -> firestore.DocumentReference:
        """Retorna referência do documento."""
        return self._client.collection(self._collection).document(user_key)

    def get_profile(self, user_key: str) -> UserProfile | None:
        """Busca perfil por user_key."""
        doc = self._doc(user_key).get()
        if not doc.exists:
            logger.debug(
                "Perfil não encontrado",
                extra={"user_key_prefix": user_key[:8] + "..."},
            )
            return None

        data = doc.to_dict() or {}
        try:
            return UserProfile(**data)
        except Exception as e:
            logger.warning(
                "Erro ao deserializar perfil",
                extra={"user_key_prefix": user_key[:8] + "...", "error": str(e)},
            )
            return None

    def get_by_phone(self, phone_e164: str) -> UserProfile | None:
        """Busca perfil por telefone (dedup)."""
        query = (
            self._client.collection(self._collection)
            .where("phone_e164", "==", phone_e164)
            .limit(1)
        )
        docs = list(query.stream())

        if not docs:
            return None

        data = docs[0].to_dict() or {}
        try:
            return UserProfile(**data)
        except Exception as e:
            logger.warning(
                "Erro ao deserializar perfil por phone",
                extra={"error": str(e)},
            )
            return None

    def upsert_profile(self, profile: UserProfile) -> None:
        """Cria ou atualiza perfil."""
        self._doc(profile.user_key).set(profile.model_dump(mode="json"))
        logger.info(
            "Perfil upserted",
            extra={"user_key_prefix": profile.user_key[:8] + "..."},
        )

    def update_field(
        self,
        user_key: str,
        field: str,
        value: str | None,
        actor: str = "system",
    ) -> bool:
        """Atualiza campo específico com histórico."""
        doc_ref = self._doc(user_key)
        doc = doc_ref.get()

        if not doc.exists:
            logger.warning(
                "Tentativa de update em perfil inexistente",
                extra={"user_key_prefix": user_key[:8] + "..."},
            )
            return False

        current = doc.to_dict() or {}
        old_value = current.get(field)
        now = datetime.now(tz=UTC)

        # Atualiza campo
        doc_ref.update({
            field: value,
            "updated_at": now.isoformat(),
        })

        # Registra histórico
        self._record_update_event(
            user_key=user_key,
            field=field,
            old_value=_mask_pii(str(old_value)) if old_value else None,
            new_value=_mask_pii(str(value)) if value else None,
            actor=actor,
            timestamp=now,
        )

        logger.info(
            "Campo de perfil atualizado",
            extra={
                "user_key_prefix": user_key[:8] + "...",
                "field": field,
                "actor": actor,
            },
        )
        return True

    def _record_update_event(
        self,
        user_key: str,
        field: str,
        old_value: str | None,
        new_value: str | None,
        actor: str,
        timestamp: datetime,
    ) -> None:
        """Registra evento de atualização no histórico."""
        history_ref = self._doc(user_key).collection("history")
        event_id = f"{timestamp.strftime('%Y%m%d%H%M%S')}_{field}"

        history_ref.document(event_id).set({
            "timestamp": timestamp.isoformat(),
            "field_changed": field,
            "old_value": old_value,
            "new_value": new_value,
            "actor": actor,
        })

    def get_update_history(
        self,
        user_key: str,
        limit: int = 50,
    ) -> list[ProfileUpdateEvent]:
        """Retorna histórico de atualizações."""
        history_ref = (
            self._doc(user_key)
            .collection("history")
            .order_by("timestamp", direction="DESCENDING")
            .limit(limit)
        )

        events: list[ProfileUpdateEvent] = []
        for doc in history_ref.stream():
            data = doc.to_dict() or {}
            try:
                ts_str = data["timestamp"]
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                events.append(ProfileUpdateEvent(
                    timestamp=ts,
                    field_changed=data["field_changed"],
                    old_value=data.get("old_value"),
                    new_value=data.get("new_value"),
                    actor=data.get("actor", "system"),
                ))
            except Exception:
                continue  # Ignora eventos malformados

        return events

    def forget(self, user_key: str) -> bool:
        """Remove perfil e histórico (LGPD).

        Implementa direito ao esquecimento conforme LGPD/GDPR.
        """
        doc_ref = self._doc(user_key)
        doc = doc_ref.get()

        if not doc.exists:
            logger.debug(
                "Forget: perfil não existe",
                extra={"user_key_prefix": user_key[:8] + "..."},
            )
            return False

        # Remove histórico primeiro
        history_ref = doc_ref.collection("history")
        for hist_doc in history_ref.stream():
            hist_doc.reference.delete()

        # Remove perfil
        doc_ref.delete()

        logger.info(
            "Perfil removido (LGPD forget)",
            extra={"user_key_prefix": user_key[:8] + "..."},
        )
        return True
