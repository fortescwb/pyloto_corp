"""Dedupe e idempotência para processamento de mensagens.

Este módulo implementa stores de deduplicação para garantir que
mensagens duplicadas não sejam processadas mais de uma vez.

Conforme TODO_01 e regras_e_padroes.md:
- Redis é o backend recomendado para produção
- TTL configurável (padrão: 7 dias)
- Fail-closed: em caso de erro, NÃO processa (segurança)
- InMemoryDedupeStore apenas para dev/testes

Referência: Funcionamento.md § DUPLICATE_OR_SPAM
"""

from __future__ import annotations

import logging
import time
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

# Protocol import — infra implements domain protocols
from pyloto_corp.domain.protocols.dedupe import DedupeProtocol
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.config.settings import Settings

logger: logging.Logger = get_logger(__name__)


class DedupeStore(DedupeProtocol):
    """Contrato abstrato para stores de deduplicação.

    Implementações devem garantir:
    - Atomicidade de marcação set-if-not-exists
    - Respeito ao TTL configurado
    - Comportamento fail-closed em produção
    """

    @abstractmethod
    def mark_if_new(self, key: str) -> bool:
        """Marca chave se não existir (set-if-not-exists).

        Args:
            key: Chave única da mensagem (ex: message_id ou hash)

        Returns:
            True se a chave foi marcada agora (evento novo)
            False se a chave já existia (duplicado)

        Raises:
            DedupeError: Em caso de falha no backend (fail-closed)
        """
        ...

    @abstractmethod
    def is_duplicate(self, key: str) -> bool:
        """Apenas verifica se chave existe, sem marcar.

        Args:
            key: Chave a verificar

        Returns:
            True se já existe, False caso contrário
        """
        ...

    @abstractmethod
    def clear(self, key: str) -> bool:
        """Remove uma chave do store (útil para testes/rollback).

        Args:
            key: Chave a remover

        Returns:
            True se removida, False se não existia
        """
        ...


class DedupeError(Exception):
    """Erro de deduplicação — indica falha no backend.

    Em modo fail-closed, a mensagem NÃO deve ser processada.
    """

    pass


@dataclass(slots=True)
class InMemoryDedupeStore(DedupeStore):
    """Dedupe em memória para desenvolvimento e testes.

    ATENÇÃO: Não usar em produção!
    - Não persiste entre restarts
    - Não funciona com múltiplas instâncias
    - Não implementa TTL real

    Útil para:
    - Testes unitários
    - Desenvolvimento local
    - Debugging
    """

    _seen: dict[str, float] = field(default_factory=dict)
    ttl_seconds: int = 604800  # 7 dias

    def seen(self, key: str, ttl: int) -> bool:
        """Verifica + marca de forma atômica em memória.

        Retorna True se já foi vista (duplicado). Se não, marca com timestamp e
        retorna False. TTL é respeitado para limpeza simulada.
        """
        self._cleanup_expired(ttl)

        if key in self._seen:
            logger.debug(
                "Dedupe hit (in-memory)",
                extra={"key": key[:16] + "...", "is_duplicate": True},
            )
            return True

        self._seen[key] = time.time()
        logger.debug(
            "Dedupe miss (in-memory)",
            extra={"key": key[:16] + "...", "is_duplicate": False},
        )
        return False

    # Compatibilidade: wrapper legado
    def mark_if_new(self, key: str) -> bool:
        """Compat wrapper: mantém semântica legada (True se novo, False se duplicado)."""
        # marcar com TTL padrão da instância
        new = not self.seen(key, self.ttl_seconds)
        return new

    def is_duplicate(self, key: str) -> bool:
        """Verifica sem marcar (compat compat)."""
        self._cleanup_expired(self.ttl_seconds)
        return key in self._seen

    def clear(self, key: str) -> bool:
        """Remove chave do store."""
        if key in self._seen:
            del self._seen[key]
            return True
        return False

    def _cleanup_expired(self, ttl: int | None = None) -> None:
        """Remove chaves expiradas (TTL simulado)."""
        if ttl is None:
            ttl = self.ttl_seconds
        now = time.time()
        expired = [k for k, ts in self._seen.items() if now - ts > ttl]
        for k in expired:
            del self._seen[k]



class RedisDedupeStore(DedupeStore):
    """Dedupe via Redis com TTL nativo e fail-closed.

    Implementação para produção que:
    - Usa SETNX para atomicidade
    - TTL nativo do Redis
    - Fail-closed em caso de erro de conexão

    Requer redis-py instalado e servidor Redis acessível.
    """

    def __init__(
        self,
        redis_url: str,
        ttl_seconds: int = 604800,
        fail_closed: bool = True,
        key_prefix: str = "dedupe:",
    ) -> None:
        """Inicializa conexão com Redis.

        Args:
            redis_url: URL de conexão (redis://host:port/db)
            ttl_seconds: Tempo de expiração das chaves
            fail_closed: Se True, levanta erro em falha de conexão
            key_prefix: Prefixo para chaves no Redis
        """
        self._redis_url = redis_url
        self._ttl_seconds = ttl_seconds
        self._fail_closed = fail_closed
        self._key_prefix = key_prefix
        self._client = None  # Lazy loading

    def _get_client(self):
        """Retorna cliente Redis (lazy loading)."""
        if self._client is None:
            try:
                # pylint: disable=import-outside-toplevel
                import redis

                self._client = redis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0,
                )
                # Testa conexão
                self._client.ping()
                logger.info(
                    "Conexão Redis estabelecida",
                    extra={"url": self._redis_url.split("@")[-1]},  # Sem credenciais
                )
            except ImportError as e:
                logger.error("redis-py não instalado")
                raise DedupeError(
                    "Dependência redis não encontrada. Instale com: pip install redis"
                ) from e
            except Exception as e:
                logger.error(
                    "Falha ao conectar ao Redis",
                    extra={"error_type": type(e).__name__},
                )
                if self._fail_closed:
                    raise DedupeError(f"Não foi possível conectar ao Redis: {e}") from e
                # Retorna None para fallback silencioso
                return None
        return self._client

    def _make_key(self, key: str) -> str:
        """Adiciona prefixo à chave."""
        return f"{self._key_prefix}{key}"

    def seen(self, key: str, ttl: int) -> bool:
        """Usa SETNX com TTL para marcar evento novo.

        Retorna True se já foi vista (duplicado). Se não, marca e retorna False.
        """
        client = self._get_client()

        if client is None:
            # Fallback silencioso (fail_closed=False)
            logger.warning("Redis indisponível, ignorando dedupe")
            return False  # conservador: não marca, assume novo

        redis_key = self._make_key(key)

        try:
            was_set = client.set(
                redis_key,
                "1",
                nx=True,
                ex=ttl if ttl is not None else self._ttl_seconds,
            )

            is_duplicate = not bool(was_set)

            logger.debug(
                "Dedupe check (Redis)",
                extra={
                    "key": key[:16] + "...",
                    "is_duplicate": is_duplicate,
                    "ttl": ttl or self._ttl_seconds,
                },
            )

            return is_duplicate

        except Exception as e:
            logger.error(
                "Erro em operação Redis",
                extra={"operation": "seen", "error_type": type(e).__name__},
            )
            if self._fail_closed:
                raise DedupeError(f"Falha ao verificar dedupe: {e}") from e
            return False

    # Compat wrapper
    def mark_if_new(self, key: str) -> bool:
        """Compat wrapper: True se novo, False se duplicado."""
        return not self.seen(key, self._ttl_seconds)

    def is_duplicate(self, key: str) -> bool:
        """Verifica existência sem modificar."""
        client = self._get_client()

        if client is None:
            return False

        redis_key = self._make_key(key)

        try:
            return client.exists(redis_key) > 0
        except Exception as e:
            logger.error(
                "Erro ao verificar duplicata",
                extra={"error_type": type(e).__name__},
            )
            if self._fail_closed:
                raise DedupeError(f"Falha ao verificar duplicata: {e}") from e
            return False

    def clear(self, key: str) -> bool:
        """Remove chave do Redis."""
        client = self._get_client()

        if client is None:
            return False

        redis_key = self._make_key(key)

        try:
            deleted = client.delete(redis_key)
            return deleted > 0
        except Exception as e:
            logger.warning(
                "Erro ao remover chave",
                extra={"error_type": type(e).__name__},
            )
            return False


def create_dedupe_store(settings: Settings | None = None):
    """Factory para criar o store de dedupe apropriado.

    Retorna uma implementação de `DedupeProtocol` com o método `seen(key, ttl)`.
    """
    if settings is None:
        from pyloto_corp.config.settings import get_settings

        settings = get_settings()

    backend = settings.dedupe_backend.lower()
    if backend == "memory":
        return _create_memory_store(settings)

    if backend == "redis":
        return _create_redis_store(settings)

    if backend == "firestore":
        return _create_firestore_store(settings)

    raise ValueError(f"Backend de dedupe não reconhecido: {backend}")


def _create_memory_store(settings: Settings) -> DedupeStore:
    """Cria store em memória (dev/testes)."""
    logger.info(
        "Usando InMemoryDedupeStore (apenas dev/testes)",
        extra={"ttl_seconds": settings.dedupe_ttl_seconds},
    )
    return InMemoryDedupeStore(ttl_seconds=settings.dedupe_ttl_seconds)


def _create_redis_store(settings: Settings) -> DedupeStore:
    """Cria store Redis com fail-closed opcional."""
    if not settings.redis_url:
        raise ValueError("REDIS_URL é obrigatório quando dedupe_backend=redis")

    fail_closed = settings.is_production or settings.is_staging

    # Namespacing forte para evitar colisões quando o mesmo Redis é compartilhado
    # entre serviços/ambientes. Não inclui PII; phone_number_id é identificador técnico.
    env = (settings.environment or "development").lower()
    phone_number_id = settings.whatsapp_phone_number_id or "unknown_phone"
    key_prefix = f"pyloto_corp:{env}:{phone_number_id}:dedupe:"

    logger.info(
        "Usando RedisDedupeStore",
        extra={
            "ttl_seconds": settings.dedupe_ttl_seconds,
            "fail_closed": fail_closed,
            "key_prefix": key_prefix,
        },
    )
    return RedisDedupeStore(
        redis_url=settings.redis_url,
        ttl_seconds=settings.dedupe_ttl_seconds,
        fail_closed=fail_closed,
        key_prefix=key_prefix,
    )


def _create_firestore_store(settings: Settings) -> DedupeStore:
    """Cria store Firestore com TTL."""
    project_id = settings.firestore_project_id or settings.gcp_project
    if not project_id:
        raise ValueError("FIRESTORE_PROJECT_ID ou GCP_PROJECT é obrigatório para dedupe_firestore")

    from google.cloud import firestore

    from pyloto_corp.infra.dedupe_firestore import FirestoreDedupeStore

    client = firestore.Client(project=project_id)
    fail_closed = settings.is_production or settings.is_staging

    logger.info(
        "Usando FirestoreDedupeStore",
        extra={"ttl_seconds": settings.dedupe_ttl_seconds, "project_id": project_id},
    )
    return FirestoreDedupeStore(
        client=client,
        ttl_seconds=settings.dedupe_ttl_seconds,
        fail_closed=fail_closed,
    )
