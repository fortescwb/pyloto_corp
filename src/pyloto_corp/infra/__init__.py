"""Camada de infraestrutura — adapters para serviços externos.

Este módulo exporta as factories principais para criação de
componentes de infraestrutura:

- Dedupe: InMemoryDedupeStore, RedisDedupeStore
- Session: InMemorySessionStore, RedisSessionStore, FirestoreSessionStore, create_session_store
- Secrets: EnvSecretProvider, SecretManagerProvider
- HTTP: HttpClient

Uso típico:
    from pyloto_corp.infra import create_dedupe_store, create_session_store

Conforme regras_e_padroes.md:
- Infraestrutura não decide regra de negócio
- Domínio não conhece infraestrutura
- Logs estruturados sem PII
"""

from pyloto_corp.infra.decision_audit_store import (
    DecisionAuditStore,
    FirestoreDecisionAuditStore,
    MemoryDecisionAuditStore,
    create_decision_audit_store,
)
from pyloto_corp.infra.dedupe import (
    DedupeError,
    DedupeStore,
    InMemoryDedupeStore,
    RedisDedupeStore,
    create_dedupe_store,
)
from pyloto_corp.infra.dedupe_firestore import FirestoreDedupeStore
from pyloto_corp.infra.http import (
    HttpClient,
    HttpClientConfig,
    HttpError,
    create_http_client,
)
from pyloto_corp.infra.inbound_processing_log import (
    FirestoreInboundProcessingLogStore,
    InboundProcessingLogStore,
    MemoryInboundProcessingLogStore,
    RedisInboundProcessingLogStore,
    create_inbound_log_store,
)
from pyloto_corp.infra.secrets import (
    EnvSecretProvider,
    SecretManagerProvider,
    SecretProvider,
    create_secret_provider,
    get_pepper_secret,
    get_whatsapp_secrets,
)
from pyloto_corp.infra.session_store import (
    FirestoreSessionStore,
    InMemorySessionStore,
    RedisSessionStore,
    SessionStore,
    SessionStoreError,
    create_session_store,
)

__all__ = [
    # Dedupe
    "DedupeStore",
    "DedupeError",
    "InMemoryDedupeStore",
    "RedisDedupeStore",
    "FirestoreDedupeStore",
    "create_dedupe_store",
    # Session
    "SessionStore",
    "SessionStoreError",
    "InMemorySessionStore",
    "RedisSessionStore",
    "FirestoreSessionStore",
    "create_session_store",
    # HTTP
    "HttpClient",
    "HttpClientConfig",
    "HttpError",
    "create_http_client",
    # Decision audit
    "DecisionAuditStore",
    "MemoryDecisionAuditStore",
    "FirestoreDecisionAuditStore",
    "create_decision_audit_store",
    # Inbound processing log
    "InboundProcessingLogStore",
    "MemoryInboundProcessingLogStore",
    "RedisInboundProcessingLogStore",
    "FirestoreInboundProcessingLogStore",
    "create_inbound_log_store",
    # Secrets
    "SecretProvider",
    "EnvSecretProvider",
    "SecretManagerProvider",
    "create_secret_provider",
    "get_pepper_secret",
    "get_whatsapp_secrets",
]
