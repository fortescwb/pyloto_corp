"""Dedupe Manager — unifica uso inbound/outbound.

O manager apenas deriva chaves namespaced e delega para o store (DedupeProtocol).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.config.settings import Settings
    from pyloto_corp.domain.protocols.dedupe import DedupeProtocol

logger = get_logger(__name__)


@dataclass(slots=True)
class DedupeManager:
    """Gerencia chaves de dedupe para inbound e outbound.

    Regras:
    - Namespaces: inbound:{message_id}, outbound:{payload_hash}
    - TTL default provém de settings.dedupe_ttl_seconds
    - Store implementa DedupeProtocol.seen(key, ttl)
    """

    store: DedupeProtocol
    settings: Settings

    def inbound(self, message_id: str, ttl: int | None = None) -> bool:
        """Verifica e marca dedupe inbound.

        Returns True se já foi vista (duplicado), False se nova.
        """
        key = f"inbound:{message_id}"
        ttl_seconds = ttl if ttl is not None else self.settings.dedupe_ttl_seconds
        logger.debug("DedupeManager inbound check", extra={"key": key[:24], "ttl": ttl_seconds})
        return self.store.seen(key, ttl_seconds)

    def outbound(self, payload_hash: str, ttl: int | None = None) -> bool:
        """Verifica e marca dedupe outbound.

        Returns True se já foi vista (duplicado), False se nova.
        """
        key = f"outbound:{payload_hash}"
        ttl_seconds = ttl if ttl is not None else self.settings.dedupe_ttl_seconds
        logger.debug("DedupeManager outbound check", extra={"key": key[:24], "ttl": ttl_seconds})
        return self.store.seen(key, ttl_seconds)
