"""Testes para factory de flood detector."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pyloto_corp.config.settings import Settings
from pyloto_corp.domain.abuse_detection import InMemoryFloodDetector, RedisFloodDetector
from pyloto_corp.infra.flood_detector_factory import (
    create_flood_detector,
    create_flood_detector_from_settings,
)


class TestCreateFloodDetector:
    """Testes para factory básica."""

    def test_create_memory_detector(self):
        """Verifica criação de detector em memória."""
        detector = create_flood_detector(
            backend="memory",
            threshold=10,
            time_window_seconds=60,
        )

        assert isinstance(detector, InMemoryFloodDetector)
        assert detector._threshold == 10
        assert detector._window == 60

    def test_create_redis_detector(self):
        """Verifica criação de detector Redis."""
        redis_client = MagicMock()
        detector = create_flood_detector(
            backend="redis",
            threshold=15,
            time_window_seconds=90,
            redis_client=redis_client,
        )

        assert isinstance(detector, RedisFloodDetector)
        assert detector._threshold == 15
        assert detector._window == 90

    def test_redis_requires_client(self):
        """Verifica que Redis backend requer cliente."""
        with pytest.raises(ValueError, match="redis_client required"):
            create_flood_detector(
                backend="redis",
                redis_client=None,
            )

    def test_invalid_backend(self):
        """Verifica rejeição de backend inválido."""
        with pytest.raises(ValueError, match="Unknown flood detector backend"):
            create_flood_detector(backend="invalid")


class TestCreateFloodDetectorFromSettings:
    """Testes para factory com settings."""

    def test_dev_uses_memory_by_default(self):
        """Verifica que desenvolvimento usa memory por padrão."""
        settings = Settings(
            environment="development",
            flood_detector_backend="memory",
            flood_threshold=5,
            flood_ttl_seconds=60,
        )

        detector = create_flood_detector_from_settings(settings)

        assert isinstance(detector, InMemoryFloodDetector)
        assert detector._threshold == 5
        assert detector._window == 60

    def test_prod_rejects_memory(self):
        """Verifica que produção rejeita memory backend."""
        settings = Settings(
            environment="production",
            flood_detector_backend="memory",
        )

        with pytest.raises(ValueError, match="unsuitable for production"):
            create_flood_detector_from_settings(settings)

    def test_staging_rejects_memory(self):
        """Verifica que staging rejeita memory backend."""
        settings = Settings(
            environment="staging",
            flood_detector_backend="memory",
        )

        with pytest.raises(ValueError, match="unsuitable for production"):
            create_flood_detector_from_settings(settings)

    def test_redis_with_provided_client(self):
        """Verifica Redis com cliente fornecido."""
        settings = Settings(
            environment="production",
            flood_detector_backend="redis",
            flood_threshold=10,
            flood_ttl_seconds=60,
        )
        redis_client = MagicMock()

        detector = create_flood_detector_from_settings(settings, redis_client=redis_client)

        assert isinstance(detector, RedisFloodDetector)
        assert detector._threshold == 10

    def test_config_values_respected(self):
        """Verifica que valores de config são respeitados."""
        settings = Settings(
            environment="development",
            flood_detector_backend="memory",
            flood_threshold=25,
            flood_ttl_seconds=120,
        )

        detector = create_flood_detector_from_settings(settings)

        assert detector._threshold == 25
        assert detector._window == 120


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
