"""Camada de infraestrutura — adapters para serviços externos.

Este módulo exporta as factories principais para criação de
componentes de infraestrutura:

- Dedupe: InMemoryDedupeStore, RedisDedupeStore
- Secrets: EnvSecretProvider, SecretManagerProvider
- HTTP: HttpClient

Uso típico:
    from pyloto_corp.infra import create_dedupe_store, create_http_client

Conforme regras_e_padroes.md:
- Infraestrutura não decide regra de negócio
- Domínio não conhece infraestrutura
- Logs estruturados sem PII
"""

from pyloto_corp.infra.dedupe import (
    DedupeError,
    DedupeStore,
    InMemoryDedupeStore,
    RedisDedupeStore,
    create_dedupe_store,
)
from pyloto_corp.infra.http import (
    HttpClient,
    HttpClientConfig,
    HttpError,
    create_http_client,
)
from pyloto_corp.infra.secrets import (
    EnvSecretProvider,
    SecretManagerProvider,
    SecretProvider,
    create_secret_provider,
    get_pepper_secret,
    get_whatsapp_secrets,
)

__all__ = [
    # Dedupe
    "DedupeStore",
    "DedupeError",
    "InMemoryDedupeStore",
    "RedisDedupeStore",
    "create_dedupe_store",
    # HTTP
    "HttpClient",
    "HttpClientConfig",
    "HttpError",
    "create_http_client",
    # Secrets
    "SecretProvider",
    "EnvSecretProvider",
    "SecretManagerProvider",
    "create_secret_provider",
    "get_pepper_secret",
    "get_whatsapp_secrets",
]