"""Shim de compatibilidade para SessionStore + factory.

Responsabilidade: reexportar contrato/implementações e oferecer create_session_store
para configuração baseada em backend. Mantém compatibilidade com importações
históricas enquanto separa responsabilidades em módulos menores.
"""

from __future__ import annotations

from typing import Literal

from pyloto_corp.infra.session_contract import SessionStore, SessionStoreError
from pyloto_corp.infra.session_store_firestore import FirestoreSessionStore
from pyloto_corp.infra.session_store_memory import InMemorySessionStore
from pyloto_corp.infra.session_store_redis import RedisSessionStore

SessionBackend = Literal["memory", "redis", "firestore"]


def create_session_store(
    backend: SessionBackend,
    *,
    client: object | None = None,
    collection: str = "sessions",
) -> SessionStore:
    backend_normalized = backend.lower()

    if backend_normalized == "memory":
        return InMemorySessionStore()

    if backend_normalized == "redis":
        if client is None:
            raise SessionStoreError("Redis client é obrigatório para backend redis")
        return RedisSessionStore(client)

    if backend_normalized == "firestore":
        if client is None:
            raise SessionStoreError("Firestore client é obrigatório para backend firestore")
        return FirestoreSessionStore(client, collection=collection)

    raise SessionStoreError(f"Backend de sessão não suportado: {backend}")


__all__ = [
    "SessionStore",
    "SessionStoreError",
    "InMemorySessionStore",
    "RedisSessionStore",
    "FirestoreSessionStore",
    "create_session_store",
]
