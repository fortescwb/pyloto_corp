from __future__ import annotations

import time

from pyloto_corp.application.dedupe.manager import DedupeManager
from pyloto_corp.config.settings import Settings
from pyloto_corp.infra.dedupe import InMemoryDedupeStore


class TestDedupeManager:
    def test_inbound_marking_and_duplicate(self) -> None:
        settings = Settings(dedupe_ttl_seconds=2)
        store = InMemoryDedupeStore()
        manager = DedupeManager(store=store, settings=settings)

        # First call: not duplicate (returns False)
        assert manager.inbound("msg1") is False

        # Second call: duplicate (returns True)
        assert manager.inbound("msg1") is True

    def test_outbound_namespace_and_ttl_override(self) -> None:
        settings = Settings(dedupe_ttl_seconds=3600)
        store = InMemoryDedupeStore()
        manager = DedupeManager(store=store, settings=settings)

        # Use override TTL small to force expiration
        assert manager.outbound("payload1", ttl=1) is False
        assert manager.outbound("payload1", ttl=1) is True

        # Wait for TTL to expire
        time.sleep(1.1)
        assert manager.outbound("payload1", ttl=1) is False
