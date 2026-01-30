"""Configurações da aplicação via variáveis de ambiente.

Todas as configurações são carregadas de env vars ou Secret Manager.
Nunca hardcode secrets ou valores sensíveis.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

# Importar create_secret_provider para uso em model_post_init
from pyloto_corp.infra.secrets import create_secret_provider

# Importar logger no topo para uso em model_post_init
from pyloto_corp.observability.logging import get_logger

# -----------------------------------------------------------------------------
# Constantes de API Meta/WhatsApp (conforme README.md e TODO_01)
# Referência: https://developers.facebook.com/docs/graph-api/changelog
# -----------------------------------------------------------------------------
GRAPH_API_VERSION: str = "v24.0"
GRAPH_API_BASE_URL: str = "https://graph.facebook.com"
GRAPH_VIDEO_BASE_URL: str = "https://graph-video.facebook.com"


class Settings(BaseSettings):
    """Configurações lidas do ambiente.

    Comentários em PT-BR são obrigatórios por diretriz do projeto.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        env_aliases={
            "gcp_location": "CLOUDTASKS_LOCATION",
            "inbound_task_queue_name": "CLOUDTASKS_QUEUE_INBOUND",
            "outbound_task_queue_name": "CLOUDTASKS_QUEUE_OUTBOUND",
        },
    )

    # Aplicação
    service_name: str = "pyloto_corp"
    version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    timezone: str = "America/Sao_Paulo"

    # WhatsApp / Meta API (versão v24.0 conforme README.md jan/2026)
    whatsapp_verify_token: str | None = None  # Para verificação de webhook
    whatsapp_webhook_secret: str | None = None  # HMAC SHA-256 secret
    whatsapp_access_token: str | None = None  # Bearer token (Secret Manager)
    whatsapp_phone_number_id: str | None = None  # ID do número registrado
    whatsapp_business_account_id: str | None = None  # ID da conta comercial
    whatsapp_api_version: str = GRAPH_API_VERSION  # Versão da Graph API
    whatsapp_api_base_url: str = GRAPH_API_BASE_URL  # URL base da API
    whatsapp_webhook_url: str | None = None  # URL pública do webhook para Firestore
    whatsapp_template_namespace: str | None = None  # Namespace para templates (optional)

    @property
    def whatsapp_api_endpoint(self) -> str:
        """Retorna a URL base completa da API WhatsApp (versão + base)."""
        return f"{self.whatsapp_api_base_url}/{self.whatsapp_api_version}"

    # Envio de mensagens (outbound)
    whatsapp_max_retries: int = 3  # Quantidade de retries em falha
    whatsapp_retry_backoff_seconds: int = 2  # Segundos para backoff exponencial
    whatsapp_request_timeout_seconds: int = 30  # Timeout HTTP
    whatsapp_max_batch_size: int = 100  # Tamanho máximo de lote
    whatsapp_circuit_breaker_enabled: bool = False  # Circuit breaker desabilitado por padrão
    whatsapp_circuit_breaker_fail_max: int = 5  # Falhas consecutivas antes de abrir
    whatsapp_circuit_breaker_reset_timeout_seconds: float = 60.0  # Tempo até half-open
    whatsapp_circuit_breaker_half_open_max_calls: int = 1  # Tentativas em half-open

    # Upload de mídia
    whatsapp_media_upload_max_mb: int = 100  # Limite de arquivo
    whatsapp_media_store_bucket: str | None = None  # GCS bucket para mídia temporária
    whatsapp_media_url_expiry_hours: int = 24  # Validade de URLs de mídia

    # Deduplicação e idempotência
    dedupe_backend: str = "memory"  # memory | redis | firestore
    redis_url: str | None = None  # Para dedupe_backend=redis
    dedupe_ttl_seconds: int = 604800  # 7 dias por padrão (retém histórico para análise)
    dedupe_batch_max_size: int = 1000  # Máximo de chaves por operação

    # Rastro de processamento inbound
    inbound_log_backend: str = "memory"  # memory | redis | firestore
    inbound_log_ttl_seconds: int = 604800

    # Filas / Cloud Tasks
    cloud_tasks_enabled: bool = False
    queue_backend: str = "memory"  # memory | cloud_tasks (dev usa memory)
    gcp_project: str | None = None  # Necessário para Cloud Tasks/Firestore
    gcp_location: str = "us-central1"
    inbound_task_queue_name: str = "whatsapp-inbound"
    outbound_task_queue_name: str = "whatsapp-outbound"
    internal_task_base_url: str | None = None  # Base URL para handlers internos
    internal_task_token: str | None = None  # Token para proteger endpoints internos
    internal_token_header: str = "X-Internal-Token"
    outbound_dedupe_backend: str = "memory"  # memory | redis | firestore

    # Armazenamento (Firestore) — conforme TODO_01
    firestore_project_id: str | None = None
    firestore_database_id: str = "(default)"
    # Collections padrão (alinhadas com TODO_01 e Funcionamento.md)
    conversations_collection: str = "conversations"
    user_profiles_collection: str = "user_profiles"
    audit_logs_collection: str = "audit_logs"
    templates_collection: str = "templates"
    exports_collection: str = "exports"

    # GCS Buckets — conforme TODO_01
    gcs_bucket_media: str | None = None  # Bucket para mídia WhatsApp
    gcs_bucket_export: str | None = None  # Bucket para exports
    gcs_media_retention_days: int = 90  # Retenção de mídia
    gcs_export_retention_days: int = 180  # Retenção de exports
    export_signed_url_expiry_days: int = 7  # Validade de URL assinada
    export_include_pii_default: bool = False  # Padrão para PII em exports

    # Pub/Sub — conforme TODO_01 (opcional, para processamento assíncrono)
    pubsub_enabled: bool = False  # Desabilitado por padrão
    pubsub_topic_inbound: str = "whatsapp-inbound-messages"
    pubsub_topic_outbound: str = "whatsapp-outbound-responses"
    pubsub_topic_handoff: str = "handoff-human"
    pubsub_topic_audit: str = "audit-events"

    # OpenAI / IA
    openai_api_key: str | None = None  # Chave da API OpenAI (Secret Manager)
    openai_model: str = "gpt-4o-mini"  # Modelo padrão (otimizado para latência)
    openai_timeout_seconds: int = 10  # Timeout para chamadas OpenAI
    openai_max_retries: int = 2  # Retries em falha
    openai_enabled: bool = False  # Feature flag: habilita LLM (fail-safe: false)

    # State selector (LLM #1)
    state_selector_enabled: bool = True
    state_selector_model: str | None = None
    state_selector_confidence_threshold: float = 0.7

    # Response generator (fase 2B)
    response_generator_enabled: bool = True
    response_generator_model: str | None = None
    response_generator_timeout_seconds: float | None = None
    response_generator_min_responses: int = 3

    # Master decider (LLM3)
    master_decider_enabled: bool = True
    master_decider_model: str | None = None
    master_decider_timeout_seconds: float | None = None
    master_decider_confidence_threshold: float = 0.7
    decision_audit_backend: str = "memory"  # memory | firestore

    # Observabilidade
    log_format: str = "json"  # json | text
    correlation_id_header: str = "X-Correlation-ID"
    enable_request_logging: bool = True
    enable_response_logging: bool = True

    # Segurança — conforme regras_e_padroes.md
    zero_trust_mode: bool = True  # Validar assinatura sempre se True
    max_message_length_chars: int = 4096
    max_contact_name_length: int = 1024
    pii_masking_enabled: bool = True

    # Sessão — conforme Funcionamento.md
    session_timeout_minutes: int = 30  # Timeout de inatividade
    session_max_intents: int = 3  # Máximo de intenções por sessão
    session_awaiting_timeout_minutes: int = 10  # Timeout em AWAITING_USER

    # Máximo de entradas armazenadas em `session.message_history` (poda segura)
    SESSION_MESSAGE_HISTORY_MAX_ENTRIES: int = 200

    # Session store backend — conforme C2
    session_store_backend: str = "memory"  # memory | redis | firestore

    # Flood detection — conforme A4 / regras_e_padroes.md
    flood_detector_backend: str = "memory"  # memory | redis
    flood_threshold: int = 10  # Limite de mensagens por janela de tempo
    flood_ttl_seconds: int = 60  # Janela de tempo (segundos) para contagem

    def validate_openai_config(self) -> list[str]:
        """Valida configuração de OpenAI.

        Se openai_enabled=True, verifica se OPENAI_API_KEY está configurado.
        Retorna lista de erros (vazia = OK).
        """
        errors: list[str] = []
        if self.openai_enabled and not self.openai_api_key:
            errors.append("OPENAI_ENABLED=true requer OPENAI_API_KEY configurado")
        return errors

    def validate_session_store_config(self) -> list[str]:
        """Valida backend de session store por ambiente.

        Em staging/prod, memory é proibido (Cloud Run é stateless).
        Retorna lista de erros (vazia = tudo OK).
        """
        errors: list[str] = []
        backend = self.session_store_backend.lower()

        # Backend deve ser válido
        valid_backends = {"memory", "redis", "firestore"}
        if backend not in valid_backends:
            errors.append(
                f"SESSION_STORE_BACKEND '{backend}' inválido. Valores válidos: {valid_backends}"
            )

        # Em staging/prod, memory é proibido (stateless Cloud Run)
        if self.is_production and backend == "memory":
            errors.append(
                "SESSION_STORE_BACKEND=memory é proibido em produção. "
                "Use 'redis' ou 'firestore' para Cloud Run stateless."
            )

        # Se staging, também rejeitar memory (preparação para prod)
        if self.environment.lower() in ("staging", "stage") and backend == "memory":
            errors.append(
                "SESSION_STORE_BACKEND=memory é proibido em staging. "
                "Configure 'redis' ou 'firestore' para compatibilidade produção."
            )

        return errors

    def validate_dedupe_backend(self) -> list[str]:
        """Valida backend de dedupe (idempotência inbound)."""
        errors: list[str] = []
        backend = self.dedupe_backend.lower()
        if backend not in {"memory", "redis", "firestore"}:
            errors.append("DEDUPE_BACKEND inválido: use memory | redis | firestore")

        if backend == "memory" and (self.is_staging or self.is_production):
            errors.append(
                "DEDUPE_BACKEND=memory é proibido em staging/production. "
                "Configure Redis ou Firestore."
            )
        if backend == "redis" and not self.redis_url:
            errors.append("DEDUPE_BACKEND=redis requer REDIS_URL configurado")
        if backend == "firestore" and not (self.firestore_project_id or self.gcp_project):
            errors.append(
                "DEDUPE_BACKEND=firestore requer FIRESTORE_PROJECT_ID ou GCP_PROJECT configurado"
            )
        return errors

    def validate_queue_config(self) -> list[str]:
        """Valida configuração de filas assíncronas (Cloud Tasks)."""
        errors: list[str] = []
        backend = self.queue_backend.lower()

        if backend not in {"memory", "cloud_tasks"}:
            errors.append("QUEUE_BACKEND inválido: use memory | cloud_tasks")

        if backend == "memory" and (self.is_staging or self.is_production):
            errors.append("QUEUE_BACKEND=memory é proibido em staging/production")

        cloud_tasks_active = backend == "cloud_tasks" or self.cloud_tasks_enabled
        if (self.is_staging or self.is_production) and not self.cloud_tasks_enabled:
            errors.append("CLOUD_TASKS_ENABLED deve ser true em staging/production")

        if cloud_tasks_active:
            if not self.gcp_project:
                errors.append("GCP_PROJECT obrigatório para Cloud Tasks")
            if not self.internal_task_base_url:
                errors.append("INTERNAL_TASK_BASE_URL obrigatório para Cloud Tasks")
            elif (self.is_staging or self.is_production) and self.internal_task_base_url.startswith(
                "http://"
            ):
                errors.append("INTERNAL_TASK_BASE_URL deve usar https em staging/production")
            if not self.internal_task_token:
                errors.append("INTERNAL_TASK_TOKEN obrigatório para Cloud Tasks")
            if not self.inbound_task_queue_name:
                errors.append("INBOUND_TASK_QUEUE_NAME obrigatório para Cloud Tasks")
            if not self.outbound_task_queue_name:
                errors.append("OUTBOUND_TASK_QUEUE_NAME obrigatório para Cloud Tasks")
            if not self.gcp_location:
                errors.append("GCP_LOCATION obrigatório para Cloud Tasks")

        return errors

    def validate_outbound_dedupe_backend(self) -> list[str]:
        """Valida backend de idempotência outbound.

        Em staging/prod, backend em memória é proibido para evitar duplicidade
        entre instâncias Cloud Run.
        """
        errors: list[str] = []
        backend = self.outbound_dedupe_backend.lower()
        valid_backends = {"memory", "redis", "firestore"}

        if backend not in valid_backends:
            errors.append(
                f"OUTBOUND_DEDUPE_BACKEND '{backend}' inválido. Valores válidos: {valid_backends}"
            )

        if backend == "memory" and (self.is_staging or self.is_production):
            errors.append(
                "OUTBOUND_DEDUPE_BACKEND=memory é proibido em staging/production. "
                "Configure Redis ou Firestore para idempotência consistente."
            )

        if backend == "redis" and not self.redis_url:
            errors.append(
                "OUTBOUND_DEDUPE_BACKEND=redis requer REDIS_URL configurado para persistência."
            )

        if backend == "firestore" and not (self.firestore_project_id or self.gcp_project):
            errors.append(
                "OUTBOUND_DEDUPE_BACKEND=firestore requer FIRESTORE_PROJECT_ID "
                "ou GCP_PROJECT configurado."
            )

        return errors

    def validate_state_selector(self) -> list[str]:
        """Valida configuração do state selector."""
        errors: list[str] = []
        if not 0 < self.state_selector_confidence_threshold <= 1:
            errors.append("STATE_SELECTOR_CONFIDENCE_THRESHOLD deve estar entre 0 e 1")
        return errors

    def validate_response_generator(self) -> list[str]:
        """Valida configuração do gerador de respostas."""
        errors: list[str] = []
        if self.response_generator_min_responses < 3:
            errors.append("RESPONSE_GENERATOR_MIN_RESPONSES deve ser >= 3")
        return errors

    def validate_master_decider(self) -> list[str]:
        """Valida configuração do decisor mestre."""
        errors: list[str] = []
        if not 0 < self.master_decider_confidence_threshold <= 1:
            errors.append("MASTER_DECIDER_CONFIDENCE_THRESHOLD deve estar entre 0 e 1")
        backend = self.decision_audit_backend.lower()
        if backend not in {"memory", "firestore"}:
            errors.append("DECISION_AUDIT_BACKEND inválido: use memory|firestore")
        if (self.is_staging or self.is_production) and backend == "memory":
            errors.append("DECISION_AUDIT_BACKEND=memory proibido em staging/production")
        if (
            self.master_decider_enabled
            and backend == "firestore"
            and not (self.firestore_project_id or self.gcp_project)
        ):
            errors.append("Decision audit firestore requer FIRESTORE_PROJECT_ID ou GCP_PROJECT")
        return errors

    def validate_inbound_log_backend(self) -> list[str]:
        """Valida backend de rastro inbound (persistente)."""

        errors: list[str] = []
        backend = self.inbound_log_backend.lower()
        valid_backends = {"memory", "redis", "firestore"}

        if backend not in valid_backends:
            errors.append(
                f"INBOUND_LOG_BACKEND '{backend}' inválido. Valores válidos: {valid_backends}"
            )

        if backend == "memory" and (self.is_staging or self.is_production):
            errors.append(
                "INBOUND_LOG_BACKEND=memory é proibido em staging/production. "
                "Configure Redis ou Firestore para rastro persistente."
            )

        if backend == "redis" and not self.redis_url:
            errors.append("INBOUND_LOG_BACKEND=redis requer REDIS_URL configurado")

        if backend == "firestore" and not (self.firestore_project_id or self.gcp_project):
            errors.append(
                "INBOUND_LOG_BACKEND=firestore requer FIRESTORE_PROJECT_ID ou GCP_PROJECT"
            )

        return errors

    @property
    def is_production(self) -> bool:
        """Retorna True se ambiente é produção."""
        return self.environment.lower() in ("production", "prod")

    @property
    def is_staging(self) -> bool:
        """Retorna True se ambiente é staging."""
        return self.environment.lower() in ("staging", "stage")

    @property
    def is_development(self) -> bool:
        """Retorna True se ambiente é desenvolvimento."""
        return self.environment.lower() in ("development", "dev", "local")

    def get_messages_endpoint(self, phone_number_id: str | None = None) -> str:
        """Retorna URL completa para envio de mensagens.

        Formato: https://graph.facebook.com/v24.0/{phone_number_id}/messages
        """
        pid = phone_number_id or self.whatsapp_phone_number_id
        if not pid:
            raise ValueError("phone_number_id é obrigatório")
        return f"{self.whatsapp_api_endpoint}/{pid}/messages"

    def validate_whatsapp_config(self) -> list[str]:
        """Valida se configurações mínimas de WhatsApp estão presentes.

        Retorna lista de erros (vazia = tudo OK).
        """
        errors: list[str] = []
        if not self.whatsapp_phone_number_id:
            errors.append("WHATSAPP_PHONE_NUMBER_ID não configurado")
        if not self.whatsapp_access_token:
            errors.append("WHATSAPP_ACCESS_TOKEN não configurado")
        if self.zero_trust_mode and not self.whatsapp_webhook_secret:
            errors.append("WHATSAPP_WEBHOOK_SECRET obrigatório em zero_trust_mode")
        return errors

    def model_post_init(self, __context: Any) -> None:
        """Carrega secrets do Secret Manager em staging/production.

        Responsabilidades:
        - Carregar secrets do Secret Manager conforme ambiente
        - Logar carregamento de cada secret (sem expor valor)
        - Validar que secrets obrigatórios foram carregados
        - Falhar explicitamente (fail-closed) em prod se faltarem secrets

        Conforme regras_e_padroes.md:
        - Nunca logar valores de secrets
        - Fail-closed em produção se segredos faltam
        - Validação rigorosa em startup
        """
        logger: logging.Logger = get_logger(__name__)
        skip_secret_manager = os.getenv("SKIP_SECRET_MANAGER", "").lower() == "true"

        # Em development, secrets podem vir de env vars ou arquivo .env
        if self.is_development:
            logger.info(
                "Usando configuração de development (secrets via env vars)",
                extra={"environment": self.environment},
            )
            return

        if self.is_staging or self.is_production:
            if skip_secret_manager:
                logger.error(
                    "SKIP_SECRET_MANAGER é proibido em staging/production",
                    extra={"environment": self.environment},
                )
                raise RuntimeError("SKIP_SECRET_MANAGER não é permitido em staging/production")

            # Em testes unitários com environment=staging/prod, evitamos chamada real
            # ao Secret Manager para manter isolamento. PYTEST_CURRENT_TEST é setado pelo pytest.
            if os.getenv("PYTEST_CURRENT_TEST"):
                logger.info(
                    "Pulando Secret Manager em ambiente de teste controlado",
                    extra={"environment": self.environment},
                )
                return

            logger.info(
                "Carregando secrets do Secret Manager",
                extra={"environment": self.environment},
            )

            project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
            if not project_id:
                logger.error(
                    "GOOGLE_CLOUD_PROJECT não configurado para Secret Manager",
                    extra={"environment": self.environment},
                )
                raise RuntimeError("GOOGLE_CLOUD_PROJECT obrigatório em staging/production")

            try:
                provider = create_secret_provider(backend="secret_manager", project_id=project_id)
            except Exception as e:
                logger.error(
                    "Falha ao criar Secret Manager provider",
                    extra={
                        "error": type(e).__name__,
                        "environment": self.environment,
                    },
                )
                raise RuntimeError(
                    f"Não foi possível inicializar Secret Manager: {type(e).__name__}"
                ) from e

            # Mapa de secrets: nome no Secret Manager → atributo em Settings
            secret_mappings = {
                "WHATSAPP_WEBHOOK_SECRET": "whatsapp_webhook_secret",
                "WHATSAPP_ACCESS_TOKEN": "whatsapp_access_token",
                "WHATSAPP_VERIFY_TOKEN": "whatsapp_verify_token",
            }

            # Carregar cada secret
            for secret_name, attr_name in secret_mappings.items():
                try:
                    if provider.secret_exists(secret_name):
                        value = provider.get_secret(secret_name)
                        if hasattr(self, attr_name):
                            setattr(self, attr_name, value)
                            logger.info(
                                "Secret carregado do Secret Manager",
                                extra={
                                    "secret_name": secret_name,
                                    "environment": self.environment,
                                },
                            )
                    else:
                        logger.warning(
                            "Secret não encontrado no Secret Manager",
                            extra={
                                "secret_name": secret_name,
                                "environment": self.environment,
                            },
                        )
                except Exception as e:
                    logger.error(
                        "Erro ao carregar secret do Secret Manager",
                        extra={
                            "secret_name": secret_name,
                            "error": type(e).__name__,
                            "environment": self.environment,
                        },
                    )
                    raise RuntimeError(
                        f"Falha ao carregar {secret_name}: {type(e).__name__}"
                    ) from e

            # Após carregar secrets, validar configuração
            logger.info("Validando configuração de WhatsApp")
            validation_errors = self.validate_whatsapp_config()
            if validation_errors:
                logger.error(
                    "Validação de configuração WhatsApp falhou",
                    extra={
                        "errors": validation_errors,
                        "environment": self.environment,
                    },
                )
                raise RuntimeError(
                    f"Configuração WhatsApp inválida: {'; '.join(validation_errors)}"
                )

            logger.info(
                "Secrets carregados e validados com sucesso",
                extra={"environment": self.environment},
            )
            return

        # Ambientes não-prod (ex.: tests) fora de dev: apenas registrar escolha
        if skip_secret_manager:
            logger.info(
                "Pulado carregamento de Secret Manager (flag SKIP_SECRET_MANAGER em env não-prod)",
                extra={"environment": self.environment},
            )
        else:
            logger.info(
                "Ambiente não-prod sem carregamento de Secret Manager",
                extra={"environment": self.environment},
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna uma instância cacheada de Settings.

    A cache garante que mesmo múltiplas injeções não criam novos objetos.
    """
    return Settings()
