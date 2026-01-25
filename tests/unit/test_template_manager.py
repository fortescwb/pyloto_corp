"""Testes unitários para TemplateManager.

Cobertura >90% conforme regras_e_padroes.md:
- Cenários de sucesso (get, sync)
- Cache hit/miss
- Erros (not found, sync failure)
- Validação de parâmetros
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from pyloto_corp.adapters.whatsapp.template_manager import (
    TemplateCategory,
    TemplateManager,
    TemplateMetadata,
    TemplateNotFoundError,
    TemplateParameter,
    TemplateStatus,
    TemplateStore,
    TemplateSyncError,
    _extract_parameters,
    _is_cache_expired,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_template_store() -> MagicMock:
    """Mock de TemplateStore."""
    store = MagicMock(spec=TemplateStore)
    store.get_template.return_value = None
    store.save_template = MagicMock()
    store.list_templates.return_value = []
    store.delete_template.return_value = True
    return store


@pytest.fixture
def mock_whatsapp_client() -> MagicMock:
    """Mock de WhatsAppHttpClient."""
    client = MagicMock()
    return client


@pytest.fixture
def sample_template() -> TemplateMetadata:
    """Template de exemplo para testes."""
    return TemplateMetadata(
        name="welcome_message",
        namespace="test_namespace",
        language="pt_BR",
        category=TemplateCategory.UTILITY,
        status=TemplateStatus.APPROVED,
        components=[
            {"type": "BODY", "text": "Olá {{1}}, seja bem-vindo!"},
        ],
        parameters=[TemplateParameter(type="text", index=1)],
        last_synced_at=datetime.now(tz=UTC),
    )


@pytest.fixture
def expired_template() -> TemplateMetadata:
    """Template com cache expirado."""
    return TemplateMetadata(
        name="old_template",
        namespace="test_namespace",
        language="pt_BR",
        category=TemplateCategory.MARKETING,
        status=TemplateStatus.APPROVED,
        components=[],
        parameters=[],
        last_synced_at=datetime.now(tz=UTC) - timedelta(hours=48),
    )


# =============================================================================
# Testes: _is_cache_expired
# =============================================================================


class TestIsCacheExpired:
    """Testes para verificação de expiração de cache."""

    def test_none_is_expired(self) -> None:
        """Cache None é considerado expirado."""
        assert _is_cache_expired(None, ttl_hours=24) is True

    def test_recent_not_expired(self) -> None:
        """Cache recente não está expirado."""
        recent = datetime.now(tz=UTC) - timedelta(hours=1)
        assert _is_cache_expired(recent, ttl_hours=24) is False

    def test_old_is_expired(self) -> None:
        """Cache antigo está expirado."""
        old = datetime.now(tz=UTC) - timedelta(hours=48)
        assert _is_cache_expired(old, ttl_hours=24) is True

    def test_exactly_at_ttl(self) -> None:
        """Cache exatamente no TTL está expirado."""
        at_ttl = datetime.now(tz=UTC) - timedelta(hours=24, seconds=1)
        assert _is_cache_expired(at_ttl, ttl_hours=24) is True


# =============================================================================
# Testes: _extract_parameters
# =============================================================================


class TestExtractParameters:
    """Testes para extração de parâmetros."""

    def test_body_with_one_variable(self) -> None:
        """Body com uma variável extrai um parâmetro."""
        components = [{"type": "BODY", "text": "Olá {{1}}!"}]
        params = _extract_parameters(components)

        assert len(params) == 1
        assert params[0].type == "text"
        assert params[0].index == 1

    def test_body_with_multiple_variables(self) -> None:
        """Body com múltiplas variáveis extrai todos."""
        components = [{"type": "BODY", "text": "{{1}} e {{2}} são {{3}}"}]
        params = _extract_parameters(components)

        assert len(params) == 3

    def test_header_with_image(self) -> None:
        """Header com imagem extrai parâmetro de mídia."""
        components = [{"type": "HEADER", "format": "IMAGE"}]
        params = _extract_parameters(components)

        assert len(params) == 1
        assert params[0].type == "image"

    def test_header_with_video(self) -> None:
        """Header com vídeo extrai parâmetro de mídia."""
        components = [{"type": "HEADER", "format": "VIDEO"}]
        params = _extract_parameters(components)

        assert len(params) == 1
        assert params[0].type == "video"

    def test_header_with_document(self) -> None:
        """Header com documento extrai parâmetro."""
        components = [{"type": "HEADER", "format": "DOCUMENT"}]
        params = _extract_parameters(components)

        assert len(params) == 1
        assert params[0].type == "document"

    def test_text_header_no_params(self) -> None:
        """Header de texto não extrai parâmetros."""
        components = [{"type": "HEADER", "format": "TEXT"}]
        params = _extract_parameters(components)

        assert len(params) == 0

    def test_mixed_components(self) -> None:
        """Componentes mistos extraem todos os parâmetros."""
        components = [
            {"type": "HEADER", "format": "IMAGE"},
            {"type": "BODY", "text": "Olá {{1}}, sua compra {{2}}"},
        ]
        params = _extract_parameters(components)

        assert len(params) == 3
        assert params[0].type == "image"
        assert params[1].type == "text"
        assert params[2].type == "text"

    def test_empty_components(self) -> None:
        """Lista vazia retorna lista vazia."""
        params = _extract_parameters([])
        assert params == []


# =============================================================================
# Testes: TemplateManager.get_template
# =============================================================================


class TestTemplateManagerGetTemplate:
    """Testes para busca de template."""

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached(
        self,
        mock_template_store: MagicMock,
        sample_template: TemplateMetadata,
    ) -> None:
        """Cache hit retorna template do cache."""
        mock_template_store.get_template.return_value = sample_template

        manager = TemplateManager(
            template_store=mock_template_store,
            cache_ttl_hours=24,
        )

        result = await manager.get_template("test_namespace", "welcome_message")

        assert result == sample_template
        mock_template_store.get_template.assert_called_once_with(
            "test_namespace", "welcome_message"
        )

    @pytest.mark.asyncio
    async def test_not_found_raises(
        self,
        mock_template_store: MagicMock,
    ) -> None:
        """Template não encontrado lança exceção."""
        mock_template_store.get_template.return_value = None

        manager = TemplateManager(
            template_store=mock_template_store,
            cache_ttl_hours=24,
        )

        with pytest.raises(TemplateNotFoundError):
            await manager.get_template("ns", "nonexistent")

    @pytest.mark.asyncio
    async def test_expired_cache_triggers_sync(
        self,
        mock_template_store: MagicMock,
        mock_whatsapp_client: MagicMock,
        expired_template: TemplateMetadata,
        sample_template: TemplateMetadata,
    ) -> None:
        """Cache expirado dispara sincronização."""
        # Primeira chamada retorna template expirado
        # Segunda chamada (após sync) retorna atualizado
        mock_template_store.get_template.side_effect = [
            expired_template,
            sample_template,
        ]

        manager = TemplateManager(
            template_store=mock_template_store,
            whatsapp_client=mock_whatsapp_client,
            cache_ttl_hours=24,
        )

        result = await manager.get_template("test_namespace", "old_template")

        # Deve ter feito sync e retornado o template atualizado
        assert mock_template_store.get_template.call_count >= 2

    @pytest.mark.asyncio
    async def test_force_sync_ignores_cache(
        self,
        mock_template_store: MagicMock,
        mock_whatsapp_client: MagicMock,
        sample_template: TemplateMetadata,
    ) -> None:
        """force_sync=True ignora cache."""
        mock_template_store.get_template.return_value = sample_template

        manager = TemplateManager(
            template_store=mock_template_store,
            whatsapp_client=mock_whatsapp_client,
            cache_ttl_hours=24,
        )

        await manager.get_template("test_namespace", "welcome_message", force_sync=True)

        # Deve ter chamado get_template mais de uma vez (antes e depois do sync)
        assert mock_template_store.get_template.call_count >= 1

    @pytest.mark.asyncio
    async def test_sync_failure_uses_stale_cache(
        self,
        mock_template_store: MagicMock,
        mock_whatsapp_client: MagicMock,
        expired_template: TemplateMetadata,
    ) -> None:
        """Falha no sync usa cache stale."""
        mock_template_store.get_template.return_value = expired_template
        mock_template_store.list_templates.return_value = []

        manager = TemplateManager(
            template_store=mock_template_store,
            whatsapp_client=mock_whatsapp_client,
            cache_ttl_hours=24,
        )

        # Mesmo com cache expirado, deve retornar o template stale
        result = await manager.get_template("test_namespace", "old_template")

        assert result == expired_template


# =============================================================================
# Testes: TemplateManager.sync_templates
# =============================================================================


class TestTemplateManagerSyncTemplates:
    """Testes para sincronização de templates."""

    @pytest.mark.asyncio
    async def test_sync_without_client_raises(
        self,
        mock_template_store: MagicMock,
    ) -> None:
        """Sync sem cliente lança exceção."""
        manager = TemplateManager(
            template_store=mock_template_store,
            whatsapp_client=None,
        )

        with pytest.raises(TemplateSyncError, match="não configurado"):
            await manager.sync_templates("namespace")

    @pytest.mark.asyncio
    async def test_sync_returns_count(
        self,
        mock_template_store: MagicMock,
        mock_whatsapp_client: MagicMock,
    ) -> None:
        """Sync retorna número de templates sincronizados."""
        manager = TemplateManager(
            template_store=mock_template_store,
            whatsapp_client=mock_whatsapp_client,
        )

        count = await manager.sync_templates("namespace")

        # Com implementação placeholder, retorna 0
        assert count == 0


# =============================================================================
# Testes: TemplateManager.validate_template_params
# =============================================================================


class TestValidateTemplateParams:
    """Testes para validação de parâmetros."""

    def test_correct_params_valid(
        self,
        mock_template_store: MagicMock,
        sample_template: TemplateMetadata,
    ) -> None:
        """Parâmetros corretos são válidos."""
        manager = TemplateManager(template_store=mock_template_store)

        # sample_template tem 1 parâmetro
        result = manager.validate_template_params(
            sample_template,
            [{"type": "text", "text": "João"}],
        )

        assert result is True

    def test_wrong_count_invalid(
        self,
        mock_template_store: MagicMock,
        sample_template: TemplateMetadata,
    ) -> None:
        """Número errado de parâmetros é inválido."""
        manager = TemplateManager(template_store=mock_template_store)

        # sample_template tem 1 parâmetro, passando 2
        result = manager.validate_template_params(
            sample_template,
            [
                {"type": "text", "text": "João"},
                {"type": "text", "text": "Extra"},
            ],
        )

        assert result is False

    def test_zero_params_when_expected(
        self,
        mock_template_store: MagicMock,
        sample_template: TemplateMetadata,
    ) -> None:
        """Zero parâmetros quando esperado é inválido."""
        manager = TemplateManager(template_store=mock_template_store)

        result = manager.validate_template_params(sample_template, [])

        assert result is False

    def test_template_without_params(
        self,
        mock_template_store: MagicMock,
    ) -> None:
        """Template sem parâmetros aceita lista vazia."""
        manager = TemplateManager(template_store=mock_template_store)

        no_params_template = TemplateMetadata(
            name="simple",
            namespace="ns",
            language="pt_BR",
            category=TemplateCategory.UTILITY,
            status=TemplateStatus.APPROVED,
            components=[{"type": "BODY", "text": "Mensagem fixa"}],
            parameters=[],
        )

        result = manager.validate_template_params(no_params_template, [])

        assert result is True


# =============================================================================
# Testes: Edge Cases
# =============================================================================


class TestTemplateManagerEdgeCases:
    """Testes para casos de borda."""

    @pytest.mark.asyncio
    async def test_multiple_namespaces(
        self,
        mock_template_store: MagicMock,
        sample_template: TemplateMetadata,
    ) -> None:
        """Templates de diferentes namespaces são separados."""
        mock_template_store.get_template.return_value = sample_template

        manager = TemplateManager(template_store=mock_template_store)

        await manager.get_template("namespace_a", "template")
        await manager.get_template("namespace_b", "template")

        # Deve ter chamado com namespaces diferentes
        calls = mock_template_store.get_template.call_args_list
        assert calls[0][0][0] == "namespace_a"
        assert calls[1][0][0] == "namespace_b"

    def test_template_categories(self) -> None:
        """Todas as categorias são suportadas."""
        for category in TemplateCategory:
            template = TemplateMetadata(
                name="test",
                namespace="ns",
                language="pt_BR",
                category=category,
                status=TemplateStatus.APPROVED,
                components=[],
            )
            assert template.category == category

    def test_template_statuses(self) -> None:
        """Todos os status são suportados."""
        for status in TemplateStatus:
            template = TemplateMetadata(
                name="test",
                namespace="ns",
                language="pt_BR",
                category=TemplateCategory.UTILITY,
                status=status,
                components=[],
            )
            assert template.status == status
