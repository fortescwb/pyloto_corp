"""Testes para bootstrap/inicialização da aplicação FastAPI.

Valida que configurações críticas (session store, dedupe) são validadas no boot.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pyloto_corp.api.app import create_app
from pyloto_corp.config.settings import Settings


class TestAppBootstrapSessionStore:
    """Testes para validação de session store no bootstrap da app."""

    def test_create_app_succeeds_with_memory_in_dev(self) -> None:
        """App deve iniciar com session_store_backend=memory em dev."""
        settings = Settings(
            environment="development",
            session_store_backend="memory",
        )
        app = create_app(settings)
        assert app is not None
        assert app.state.session_store is not None

    def test_create_app_succeeds_with_redis_in_prod(self) -> None:
        """App deve iniciar com session_store_backend=redis em prod com URL válida."""
        mock_redis_client = MagicMock()
        mock_flood_detector = MagicMock()
        settings = Settings(
            environment="production",
            session_store_backend="redis",
            flood_detector_backend="redis",
            redis_url="redis://localhost:6379",
            queue_backend="cloud_tasks",
            cloud_tasks_enabled=True,
            gcp_project="test-project",
            internal_task_base_url="https://internal.test",
            internal_task_token="token",
            dedupe_backend="redis",
            outbound_dedupe_backend="redis",
            inbound_log_backend="redis",
            decision_audit_backend="firestore",
        )
        # Mock no local onde são usados (pyloto_corp.api.app)
        with (
            patch("pyloto_corp.api.app._create_redis_client", return_value=mock_redis_client),
            patch(
                "pyloto_corp.api.app.create_flood_detector_from_settings",
                return_value=mock_flood_detector,
            ),
            patch("pyloto_corp.api.app._create_tasks_dispatcher", return_value=MagicMock()),
            patch("pyloto_corp.api.app.create_decision_audit_store", return_value=MagicMock()),
        ):
            app = create_app(settings)
            assert app is not None
            assert app.state.session_store is not None

    def test_create_app_fails_with_redis_without_url(self) -> None:
        """App DEVE FALHAR se backend=redis mas REDIS_URL não configurado."""
        settings = Settings(
            environment="production",
            session_store_backend="redis",
            redis_url=None,
            queue_backend="cloud_tasks",
            cloud_tasks_enabled=True,
            gcp_project="test-project",
            internal_task_base_url="https://internal.test",
            internal_task_token="token",
            dedupe_backend="redis",
            outbound_dedupe_backend="redis",
            inbound_log_backend="redis",
        )
        with (
            patch("pyloto_corp.api.app._create_tasks_dispatcher", return_value=MagicMock()),
            pytest.raises(ValueError, match="REDIS_URL"),
        ):
            create_app(settings)

    def test_create_app_fails_with_memory_in_prod(self) -> None:
        """App DEVE FALHAR no boot se session_store_backend=memory em production."""
        settings = Settings(
            environment="production",
            session_store_backend="memory",
            queue_backend="cloud_tasks",
            cloud_tasks_enabled=True,
            gcp_project="test-project",
            internal_task_base_url="https://internal.test",
            internal_task_token="token",
            inbound_log_backend="redis",
            redis_url="redis://localhost:6379",
        )
        with pytest.raises(ValueError, match="SESSION_STORE_BACKEND"):
            create_app(settings)

    def test_create_app_fails_with_memory_in_staging(self) -> None:
        """App DEVE FALHAR no boot se session_store_backend=memory em staging."""
        settings = Settings(
            environment="staging",
            session_store_backend="memory",
            queue_backend="cloud_tasks",
            cloud_tasks_enabled=True,
            gcp_project="test-project",
            internal_task_base_url="https://internal.test",
            internal_task_token="token",
            inbound_log_backend="redis",
            redis_url="redis://localhost:6379",
        )
        with pytest.raises(ValueError, match="SESSION_STORE_BACKEND"):
            create_app(settings)

    def test_create_app_fails_with_invalid_backend(self) -> None:
        """App DEVE FALHAR no boot se backend for inválido."""
        settings = Settings(
            environment="development",
            session_store_backend="invalid_backend",
        )
        with pytest.raises(ValueError, match="SESSION_STORE_BACKEND"):
            create_app(settings)

    def test_create_app_error_includes_environment(self) -> None:
        """Mensagem de erro deve incluir ambiente para diagnóstico."""
        settings = Settings(
            environment="production",
            session_store_backend="memory",
            queue_backend="cloud_tasks",
            cloud_tasks_enabled=True,
            gcp_project="test-project",
            internal_task_base_url="https://internal.test",
            internal_task_token="token",
        )
        with pytest.raises(ValueError) as exc_info:
            create_app(settings)
        error_msg = str(exc_info.value)
        assert "production" in error_msg.lower()
        assert "session_store_backend" in error_msg.lower()

    def test_create_app_error_does_not_expose_secrets(self) -> None:
        """Mensagem de erro NÃO deve conter secrets (tokens, chaves)."""
        settings = Settings(
            environment="production",
            session_store_backend="memory",
            whatsapp_access_token="secret_token_12345",
            queue_backend="cloud_tasks",
            cloud_tasks_enabled=True,
            gcp_project="test-project",
            internal_task_base_url="https://internal.test",
            internal_task_token="token",
        )
        with pytest.raises(ValueError) as exc_info:
            create_app(settings)
        error_msg = str(exc_info.value)
        assert "secret_token_12345" not in error_msg


def test_skip_secret_manager_forbidden_in_staging(monkeypatch: pytest.MonkeyPatch) -> None:
    """SKIP_SECRET_MANAGER=true deve falhar em staging/prod."""
    monkeypatch.setenv("SKIP_SECRET_MANAGER", "true")
    with pytest.raises(RuntimeError, match="SKIP_SECRET_MANAGER"):
        Settings(environment="staging")
