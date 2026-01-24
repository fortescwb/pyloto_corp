"""Configurações da aplicação via variáveis de ambiente.

Todas as configurações são carregadas de env vars ou Secret Manager.
Nunca hardcode secrets ou valores sensíveis.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

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

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

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

    # Upload de mídia
    whatsapp_media_upload_max_mb: int = 100  # Limite de arquivo
    whatsapp_media_store_bucket: str | None = None  # GCS bucket para mídia temporária
    whatsapp_media_url_expiry_hours: int = 24  # Validade de URLs de mídia

    # Deduplicação e idempotência
    dedupe_backend: str = "memory"  # memory | redis | firestore
    redis_url: str | None = None  # Para dedupe_backend=redis
    dedupe_ttl_seconds: int = 86400  # 24 horas por padrão
    dedupe_batch_max_size: int = 1000  # Máximo de chaves por operação

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

    @property
    def is_production(self) -> bool:
        """Retorna True se ambiente é produção."""
        return self.environment.lower() in ("production", "prod")

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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna uma instância cacheada de Settings.

    A cache garante que mesmo múltiplas injeções não criam novos objetos.
    """
    return Settings()
