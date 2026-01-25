"""Gerenciamento de templates WhatsApp com cache e sincronização.

Responsabilidades:
- Carregar templates do Firestore (cache local)
- Sincronizar templates da Graph API periodicamente
- Validar estrutura de template
- Retornar metadados de template (parâmetros, categoria)
- Implementar cache com TTL

Conforme regras_e_padroes.md:
- Máximo 200 linhas por arquivo
- Máximo 50 linhas por função
- SRP: responsabilidade única
- Zero-trust: validação rigorosa
- Logs estruturados sem PII
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Protocol

from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.adapters.whatsapp.http_client import WhatsAppHttpClient
    from pyloto_corp.config.settings import Settings

logger: logging.Logger = get_logger(__name__)


class TemplateCategory(str, Enum):
    """Categorias de template conforme Meta."""

    MARKETING = "MARKETING"
    UTILITY = "UTILITY"
    AUTHENTICATION = "AUTHENTICATION"


class TemplateStatus(str, Enum):
    """Status de aprovação de template."""

    APPROVED = "APPROVED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class TemplateParameter:
    """Parâmetro de template."""

    type: str  # text, currency, date_time, image, document, video
    index: int  # Posição no template (1-based)


@dataclass
class TemplateMetadata:
    """Metadados de template do WhatsApp."""

    name: str
    namespace: str
    language: str
    category: TemplateCategory
    status: TemplateStatus
    components: list[dict]  # header, body, footer, buttons
    parameters: list[TemplateParameter] = field(default_factory=list)
    last_synced_at: datetime | None = None


class TemplateStore(Protocol):
    """Contrato para persistência de templates."""

    def get_template(self, namespace: str, name: str) -> TemplateMetadata | None:
        """Busca template por namespace e nome."""
        ...

    def save_template(self, template: TemplateMetadata) -> None:
        """Persiste template."""
        ...

    def list_templates(self, namespace: str) -> list[TemplateMetadata]:
        """Lista todos os templates de um namespace."""
        ...

    def delete_template(self, namespace: str, name: str) -> bool:
        """Remove template."""
        ...


class TemplateManagerError(Exception):
    """Erro genérico de gerenciamento de templates."""

    pass


class TemplateNotFoundError(TemplateManagerError):
    """Template não encontrado."""

    pass


class TemplateSyncError(TemplateManagerError):
    """Erro ao sincronizar templates."""

    pass


def _is_cache_expired(last_synced: datetime | None, ttl_hours: int) -> bool:
    """Verifica se cache expirou."""
    if last_synced is None:
        return True
    now = datetime.now(tz=UTC)
    return now - last_synced > timedelta(hours=ttl_hours)


def _extract_parameters(components: list[dict]) -> list[TemplateParameter]:
    """Extrai parâmetros dos componentes do template."""
    params: list[TemplateParameter] = []
    index = 1

    for component in components:
        comp_type = component.get("type", "").upper()

        # Body tem variáveis {{1}}, {{2}}, etc.
        if comp_type == "BODY":
            text = component.get("text", "")
            # Conta {{n}} no texto
            import re

            matches = re.findall(r"\{\{(\d+)\}\}", text)
            for _ in matches:
                params.append(TemplateParameter(type="text", index=index))
                index += 1

        # Header pode ter mídia
        if comp_type == "HEADER":
            header_format = component.get("format", "TEXT")
            if header_format in ("IMAGE", "VIDEO", "DOCUMENT"):
                params.append(TemplateParameter(type=header_format.lower(), index=index))
                index += 1

    return params


class TemplateManager:
    """Gerencia templates WhatsApp com cache e sincronização.

    Fluxo:
    1. Busca template no cache (Firestore)
    2. Verifica TTL do cache
    3. Se expirado, sincroniza da API
    4. Retorna metadados validados
    """

    def __init__(
        self,
        template_store: TemplateStore,
        whatsapp_client: WhatsAppHttpClient | None = None,
        settings: Settings | None = None,
        cache_ttl_hours: int = 24,
    ) -> None:
        """Inicializa TemplateManager.

        Args:
            template_store: Store para persistência (Firestore)
            whatsapp_client: Cliente para API Meta
            settings: Configurações da aplicação
            cache_ttl_hours: TTL do cache em horas (padrão: 24h)
        """
        self._store = template_store
        self._client = whatsapp_client
        self._settings = settings
        self._cache_ttl_hours = cache_ttl_hours

    async def get_template(
        self,
        namespace: str,
        name: str,
        force_sync: bool = False,
    ) -> TemplateMetadata:
        """Busca template com cache.

        Args:
            namespace: Namespace do WABA
            name: Nome do template
            force_sync: Se True, ignora cache e sincroniza

        Returns:
            TemplateMetadata

        Raises:
            TemplateNotFoundError: Se template não existe
        """
        # Busca no cache
        cached = self._store.get_template(namespace, name)

        # Verifica se precisa sincronizar
        needs_sync = force_sync or (
            cached is not None
            and _is_cache_expired(cached.last_synced_at, self._cache_ttl_hours)
        )

        if needs_sync and self._client:
            logger.debug(
                "Template cache expirado, sincronizando",
                extra={"namespace": namespace, "name": name},
            )
            try:
                await self._sync_single_template(namespace, name)
                cached = self._store.get_template(namespace, name)
            except TemplateSyncError:
                # Se falhar sync mas tem cache, usa cache stale
                if cached:
                    logger.warning(
                        "Sync falhou, usando cache stale",
                        extra={"namespace": namespace, "name": name},
                    )
                else:
                    raise

        if cached is None:
            raise TemplateNotFoundError(f"Template não encontrado: {namespace}/{name}")

        return cached

    async def sync_templates(self, namespace: str) -> int:
        """Sincroniza todos os templates de um namespace.

        Args:
            namespace: Namespace do WABA

        Returns:
            Número de templates sincronizados

        Raises:
            TemplateSyncError: Se falha na sincronização
        """
        if not self._client:
            raise TemplateSyncError("WhatsApp client não configurado")

        logger.info("Iniciando sincronização de templates", extra={"namespace": namespace})

        try:
            # Implementação simplificada - em produção, usar pagination
            templates_data = await self._fetch_templates_from_api(namespace)
            count = 0

            for tmpl_data in templates_data:
                template = self._parse_template_response(tmpl_data, namespace)
                self._store.save_template(template)
                count += 1

            logger.info(
                "Sincronização de templates concluída",
                extra={"namespace": namespace, "count": count},
            )
            return count

        except Exception as e:
            logger.error(
                "Falha na sincronização de templates",
                extra={"namespace": namespace, "error": str(e)},
            )
            raise TemplateSyncError(f"Sync falhou: {e}") from e

    async def _sync_single_template(self, namespace: str, name: str) -> None:
        """Sincroniza um único template."""
        # Em produção, fazer GET específico
        # Por ora, sincroniza todos e filtra
        await self.sync_templates(namespace)

    async def _fetch_templates_from_api(self, namespace: str) -> list[dict]:
        """Busca templates da API Meta (placeholder)."""
        # TODO: Implementar chamada real à Graph API
        # GET /{waba_id}/message_templates
        logger.debug(
            "Fetch de templates pendente de implementação",
            extra={"namespace": namespace},
        )
        return []

    def _parse_template_response(self, data: dict, namespace: str) -> TemplateMetadata:
        """Converte resposta da API em TemplateMetadata."""
        components = data.get("components", [])
        return TemplateMetadata(
            name=data.get("name", ""),
            namespace=namespace,
            language=data.get("language", "pt_BR"),
            category=TemplateCategory(data.get("category", "UTILITY")),
            status=TemplateStatus(data.get("status", "PENDING")),
            components=components,
            parameters=_extract_parameters(components),
            last_synced_at=datetime.now(tz=UTC),
        )

    def validate_template_params(
        self,
        template: TemplateMetadata,
        provided_params: list[dict],
    ) -> bool:
        """Valida se parâmetros fornecidos são compatíveis com template.

        Args:
            template: Metadados do template
            provided_params: Parâmetros a validar

        Returns:
            True se válidos
        """
        expected_count = len(template.parameters)
        actual_count = len(provided_params)

        if expected_count != actual_count:
            logger.warning(
                "Número de parâmetros incorreto",
                extra={
                    "template": template.name,
                    "expected": expected_count,
                    "actual": actual_count,
                },
            )
            return False

        return True
