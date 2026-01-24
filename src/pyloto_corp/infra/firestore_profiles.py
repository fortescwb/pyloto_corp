"""Firestore store para UserProfile."""

from __future__ import annotations

from google.cloud import firestore

from pyloto_corp.domain.profile import UserProfile, UserProfileStore


class FirestoreUserProfileStore(UserProfileStore):
    def __init__(self, client: firestore.Client, collection: str = "profiles") -> None:
        self._client = client
        self._collection = collection

    def _doc(self, user_key: str) -> firestore.DocumentReference:
        return self._client.collection(self._collection).document(user_key)

    def get_profile(self, user_key: str) -> UserProfile | None:
        doc = self._doc(user_key).get()
        if not doc.exists:
            return None
        return UserProfile(**(doc.to_dict() or {}))

    def upsert_profile(self, profile: UserProfile) -> None:
        self._doc(profile.user_key).set(profile.model_dump())
