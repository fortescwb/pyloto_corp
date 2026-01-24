"""Testes unitários para config/settings.py.

Valida configurações, constantes e métodos de validação.
"""

from __future__ import annotations

import pytest

from pyloto_corp.config.settings import (
    GRAPH_API_BASE_URL,
    GRAPH_API_VERSION,
    GRAPH_VIDEO_BASE_URL,
    Settings,
    get_settings,
)


class TestGraphApiConstants:
    """Testes para constantes da Graph API Meta."""

    def test_graph_api_version_is_v24(self) -> None:
        """Versão deve ser v24.0 conforme README.md jan/2026."""
        assert GRAPH_API_VERSION == "v24.0"

    def test_graph_api_base_url_is_facebook(self) -> None:
        """URL base deve ser graph.facebook.com (não instagram)."""
        assert GRAPH_API_BASE_URL == "https://graph.facebook.com"
        assert "instagram" not in GRAPH_API_BASE_URL.lower()

    def test_graph_video_base_url(self) -> None:
        """URL de vídeo usa domínio separado."""
        assert GRAPH_VIDEO_BASE_URL == "https://graph-video.facebook.com"


class TestSettingsDefaults:
    """Testes para valores padrão de Settings."""

    def test_default_environment_is_development(self) -> None:
        """Ambiente padrão deve ser development."""
        s = Settings()
        assert s.environment == "development"
        assert s.is_development is True
        assert s.is_production is False

    def test_default_dedupe_backend_is_memory(self) -> None:
        """Backend de dedupe padrão é memory (para dev)."""
        s = Settings()
        assert s.dedupe_backend == "memory"

    def test_default_zero_trust_mode_is_true(self) -> None:
        """Zero-trust deve estar habilitado por padrão."""
        s = Settings()
        assert s.zero_trust_mode is True

    def test_default_session_max_intents(self) -> None:
        """Máximo de 3 intenções por sessão (conforme Funcionamento.md)."""
        s = Settings()
        assert s.session_max_intents == 3

    def test_default_session_timeout(self) -> None:
        """Timeout de sessão padrão é 30 minutos."""
        s = Settings()
        assert s.session_timeout_minutes == 30


class TestSettingsApiEndpoint:
    """Testes para endpoint da API WhatsApp."""

    def test_whatsapp_api_endpoint_property(self) -> None:
        """Endpoint deve combinar base URL + versão."""
        s = Settings()
        assert s.whatsapp_api_endpoint == "https://graph.facebook.com/v24.0"

    def test_get_messages_endpoint(self) -> None:
        """URL de mensagens deve incluir phone_number_id."""
        s = Settings(whatsapp_phone_number_id="123456789")
        expected = "https://graph.facebook.com/v24.0/123456789/messages"
        assert s.get_messages_endpoint() == expected

    def test_get_messages_endpoint_with_override(self) -> None:
        """Permite override do phone_number_id."""
        s = Settings(whatsapp_phone_number_id="default")
        expected = "https://graph.facebook.com/v24.0/override/messages"
        assert s.get_messages_endpoint("override") == expected

    def test_get_messages_endpoint_raises_without_phone_id(self) -> None:
        """Deve levantar erro se phone_number_id não configurado."""
        s = Settings()
        with pytest.raises(ValueError, match="phone_number_id"):
            s.get_messages_endpoint()


class TestSettingsValidation:
    """Testes para validação de configurações WhatsApp."""

    def test_validate_returns_errors_without_phone_id(self) -> None:
        """Erro se phone_number_id não configurado."""
        s = Settings()
        errors = s.validate_whatsapp_config()
        assert any("PHONE_NUMBER_ID" in e for e in errors)

    def test_validate_returns_errors_without_access_token(self) -> None:
        """Erro se access_token não configurado."""
        s = Settings()
        errors = s.validate_whatsapp_config()
        assert any("ACCESS_TOKEN" in e for e in errors)

    def test_validate_requires_webhook_secret_in_zero_trust(self) -> None:
        """Em zero_trust_mode, webhook_secret é obrigatório."""
        s = Settings(
            whatsapp_phone_number_id="123",
            whatsapp_access_token="token",
            zero_trust_mode=True,
        )
        errors = s.validate_whatsapp_config()
        assert any("WEBHOOK_SECRET" in e for e in errors)

    def test_validate_passes_with_full_config(self) -> None:
        """Sem erros quando tudo configurado."""
        s = Settings(
            whatsapp_phone_number_id="123",
            whatsapp_access_token="token",
            whatsapp_webhook_secret="secret",
            zero_trust_mode=True,
        )
        errors = s.validate_whatsapp_config()
        assert errors == []


class TestSettingsCollections:
    """Testes para nomes de collections Firestore."""

    def test_default_collection_names(self) -> None:
        """Collections padrão conforme TODO_01."""
        s = Settings()
        assert s.conversations_collection == "conversations"
        assert s.user_profiles_collection == "user_profiles"
        assert s.audit_logs_collection == "audit_logs"
        assert s.templates_collection == "templates"
        assert s.exports_collection == "exports"


class TestGetSettings:
    """Testes para função get_settings cacheada."""

    def test_get_settings_returns_same_instance(self) -> None:
        """get_settings deve retornar mesma instância (cache)."""
        # Limpa cache para teste isolado
        get_settings.cache_clear()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
