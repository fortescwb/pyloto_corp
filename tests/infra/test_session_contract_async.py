import pytest

from pyloto_corp.application.session import SessionState
from pyloto_corp.infra.session_contract_async import (
    AsyncSessionStore,
    AsyncSessionStoreError,
)


class InMemoryAsyncSessionStore(AsyncSessionStore):
    """In-memory implementation for exercising the abstract contract."""

    def __init__(self):
        self.sessions: dict[str, tuple[SessionState, int]] = {}

    async def save(self, session: SessionState, ttl_seconds: int = 7200) -> None:
        self.sessions[session.session_id] = (session, ttl_seconds)

    async def load(self, session_id: str) -> SessionState | None:
        return self.sessions.get(session_id, (None, 0))[0]

    async def delete(self, session_id: str) -> bool:
        return self.sessions.pop(session_id, None) is not None

    async def exists(self, session_id: str) -> bool:
        return session_id in self.sessions


@pytest.mark.asyncio
async def test_async_session_store_persists_and_deletes_sessions():
    store = InMemoryAsyncSessionStore()
    session = SessionState(session_id="s1")

    await store.save(session)
    assert await store.exists("s1") is True
    loaded = await store.load("s1")
    assert loaded is session

    deleted = await store.delete("s1")
    assert deleted is True
    assert await store.exists("s1") is False
    assert await store.load("s1") is None


@pytest.mark.asyncio
async def test_async_session_store_respects_ttl_override():
    store = InMemoryAsyncSessionStore()
    session = SessionState(session_id="s2")

    await store.save(session, ttl_seconds=123)
    assert store.sessions["s2"][1] == 123

    await store.save(session)  # default overwrite
    assert store.sessions["s2"][1] == 7200


def test_async_session_store_error_repr():
    error = AsyncSessionStoreError("failure")
    assert "failure" in str(error)
