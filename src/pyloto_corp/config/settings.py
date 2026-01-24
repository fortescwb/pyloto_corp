"""Configurações da aplicação via variáveis de ambiente.

Todas as configurações são carregadas de env vars ou Secret Manager.
Nunca hardcode secrets ou valores sensíveis.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações lidas do ambiente.

    Comentários em PT-BR são obrigatórios por diretriz do projeto.
    """

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    # Aplicação
    service_name: str = "pyloto_corp"
    version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    timezone: str = "America/Sao_Paulo"

    # WhatsApp / Meta API
    whatsapp_verify_token: str | None = None  # Para verificação de webhook
    whatsapp_webhook_secret: str | None = None  # HMAC SHA-256 secret
    whatsapp_access_token: str | None = None  # Bearer token (Secret Manager)
    whatsapp_phone_number_id: str | None = None  # ID do número registrado
    whatsapp_business_account_id: str | None = None  # ID da conta comercial
    whatsapp_api_endpoint: str = "https://graph.instagram.com/v20.0"  # Versão Meta API
    whatsapp_webhook_url: str | None = None  # URL pública do webhook para Firestore
    whatsapp_template_namespace: str | None = None  # Namespace para templates (optional)

    # Envio de mensagens (outbound)
    whatsapp_max_retries: int = 3  # Quantidade de retries em falha
    whatsapp_retry_backoff_seconds: int = 2  # Segundos para backoff exponencial
    whatsapp_request_timeout_seconds: int = 30  # Timeout HTTP
    whatsapp_max_batch_size: int = 100  # Tamanho máximo de lote

    # Upload de mídia
    whatsapp_media_upload_max_mb: int = 100  # Limite de arquivo
    whatsapp_media_store_bucket: str | None = None  # GCS bucket para mídia temporária
    whatsapp_media_url_expiry_hours: int = 24  # Validade de URLs de mídia

    # Deduplicação e idempotência
    dedupe_backend: str = "memory"  # memory | redis | firestore
    redis_url: str | None = None  # Para dedupe_backend=redis
    dedupe_ttl_seconds: int = 86400  # 24 horas por padrão
    dedupe_batch_max_size: int = 1000  # Máximo de chaves por operação

    # Armazenamento (Firestore)
    firestore_project_id: str | None = None
    firestore_database_id: str = "(default)"
    conversations_collection: str = "conversations"
    audit_collection: str = "audit"
    export_bucket: str | None = None  # GCS bucket para exports
    export_include_pii_default: bool = False  # Padrão para PII em exports

    # Observabilidade
    log_format: str = "json"  # json | text
    correlation_id_header: str = "X-Correlation-ID"
    enable_request_logging: bool = True
    enable_response_logging: bool = True

    # Segurança
    zero_trust_mode: bool = True  # Validar assinatura sempre se True
    max_message_length_chars: int = 4096
    max_contact_name_length: int = 1024
    pii_masking_enabled: bool = True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna uma instância cacheada de Settings.

    A cache garante que mesmo múltiplas injeções não criam novos objetos.
    """
    return Settings()
