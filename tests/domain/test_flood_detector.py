"""Testes para detecção de flood — InMemory e Redis.

Conforme A4 — Flood/rate-limit em ambiente distribuído (Redis).
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from pyloto_corp.domain.abuse_detection import (
    FloodDetectionResult,
    InMemoryFloodDetector,
    RedisFloodDetector,
)


@pytest.fixture
def in_memory_detector() -> InMemoryFloodDetector:
    """Cria um detector de flood em memória para testes."""
    return InMemoryFloodDetector(threshold=5, time_window_seconds=10)


@pytest.fixture
def redis_client_stub() -> MagicMock:
    """Cria um stub de cliente Redis para testes."""
    client = MagicMock()
    # Simular contador de chaves (INCR)
    client.incr = MagicMock(side_effect=lambda key: _incr_stub(key, client))
    # Simular TTL (EXPIRE)
    client.expire = MagicMock(return_value=True)
    return client


# Dicionário global para simular estado do Redis no stub
_redis_state: dict[str, int] = {}


def _incr_stub(key: str, client: MagicMock) -> int:
    """Simula INCR do Redis."""
    global _redis_state
    if key not in _redis_state:
        _redis_state[key] = 0
    _redis_state[key] += 1
    return _redis_state[key]


@pytest.fixture
def redis_detector(redis_client_stub: MagicMock) -> RedisFloodDetector:
    """Cria um detector de flood com Redis stub."""
    return RedisFloodDetector(
        redis_client=redis_client_stub,
        threshold=5,
        time_window_seconds=10,
    )


class TestInMemoryFloodDetector:
    """Testes para detector de flood em memória."""

    def test_no_flood_under_threshold(self, in_memory_detector: InMemoryFloodDetector):
        """Verifica que não há flood quando abaixo do threshold."""
        session_id = "test-session-001"
        threshold = in_memory_detector._threshold

        # Adicionar (threshold - 1) eventos
        for i in range(threshold - 1):
            result = in_memory_detector.check_and_record(session_id)
            assert not result.is_flooded
            assert result.message_count == i + 1

    def test_flood_at_threshold(self, in_memory_detector: InMemoryFloodDetector):
        """Verifica que há flood quando atinge o threshold."""
        session_id = "test-session-002"
        threshold = in_memory_detector._threshold

        # Adicionar threshold eventos
        for i in range(threshold):
            result = in_memory_detector.check_and_record(session_id)
            if i < threshold - 1:
                assert not result.is_flooded
            else:
                assert result.is_flooded
                assert result.message_count == threshold

    def test_flood_multiple_sessions_isolated(self, in_memory_detector: InMemoryFloodDetector):
        """Verifica que flood em uma sessão não afeta outra."""
        session_1 = "session-001"
        session_2 = "session-002"
        threshold = in_memory_detector._threshold

        # Atingir threshold na sessão 1
        for _i in range(threshold):
            result = in_memory_detector.check_and_record(session_1)

        assert result.is_flooded

        # Sessão 2 deve estar limpa
        result_2 = in_memory_detector.check_and_record(session_2)
        assert not result_2.is_flooded
        assert result_2.message_count == 1

    def test_ttl_window_respected(self, in_memory_detector: InMemoryFloodDetector):
        """Verifica que eventos expiram após TTL."""
        session_id = "test-session-ttl"
        threshold = in_memory_detector._threshold
        window = in_memory_detector._window

        # Adicionar threshold eventos
        now = time.time()
        for _i in range(threshold):
            in_memory_detector.check_and_record(session_id, timestamp=now)

        # Simular passagem de tempo (além da janela)
        future = now + window + 1
        result = in_memory_detector.check_and_record(session_id, timestamp=future)

        # Deve contar apenas o novo evento (antigos expiraram)
        assert not result.is_flooded
        assert result.message_count == 1


class TestRedisFloodDetector:
    """Testes para detector de flood via Redis."""

    def test_redis_detector_creation(self, redis_detector: RedisFloodDetector):
        """Verifica criação do detector Redis."""
        assert redis_detector._threshold == 5
        assert redis_detector._window == 10
        assert redis_detector._redis is not None

    def test_redis_flood_detection(self, redis_detector: RedisFloodDetector):
        """Verifica detecção de flood no Redis."""
        global _redis_state
        _redis_state.clear()

        session_id = "test-session-redis-001"
        threshold = redis_detector._threshold

        # Adicionar events até threshold
        for i in range(threshold):
            result = redis_detector.check_and_record(session_id)
            assert result.message_count == i + 1
            if i < threshold - 1:
                assert not result.is_flooded
            else:
                assert result.is_flooded

    def test_redis_client_called_correctly(
        self, redis_detector: RedisFloodDetector, redis_client_stub: MagicMock
    ):
        """Verifica que Redis client é chamado com chave correta."""
        session_id = "test-session-redis-002"
        expected_key = f"flood:{session_id}"

        redis_detector.check_and_record(session_id)

        # Verificar que incr foi chamado
        redis_client_stub.incr.assert_called()

        # Verificar que expire foi chamado com TTL correto
        redis_client_stub.expire.assert_called_with(expected_key, redis_detector._window)

    def test_redis_error_handling(self, redis_client_stub: MagicMock):
        """Verifica fallback seguro em caso de erro Redis."""
        # Simular erro no Redis
        redis_client_stub.incr.side_effect = Exception("Redis connection failed")

        detector = RedisFloodDetector(
            redis_client=redis_client_stub,
            threshold=5,
            time_window_seconds=10,
        )

        session_id = "test-session-redis-error"
        result = detector.check_and_record(session_id)

        # Em caso de erro, deve retornar is_flooded=False (fail-safe)
        assert not result.is_flooded
        assert result.message_count == 0


class TestFloodDetectorParametrized:
    """Testes parametrizados para ambos detectores."""

    @pytest.mark.parametrize(
        "threshold,expected_flooded",
        [
            (3, True),  # Threshold 3, enviar 3 deve gerar flood
            (5, False),  # Threshold 5, enviar 3 não deve gerar flood
        ],
    )
    def test_threshold_variations(
        self,
        in_memory_detector: InMemoryFloodDetector,
        threshold: int,
        expected_flooded: bool,
    ):
        """Testa diferentes thresholds."""
        detector = InMemoryFloodDetector(threshold=threshold, time_window_seconds=10)
        session_id = f"test-threshold-{threshold}"

        # Enviar 3 mensagens
        result = None
        for _ in range(3):
            result = detector.check_and_record(session_id)

        assert result.is_flooded == expected_flooded

    def test_result_structure(self, in_memory_detector: InMemoryFloodDetector):
        """Verifica estrutura de FloodDetectionResult."""
        session_id = "test-result-struct"
        result = in_memory_detector.check_and_record(session_id)

        assert isinstance(result, FloodDetectionResult)
        assert isinstance(result.is_flooded, bool)
        assert isinstance(result.message_count, int)
        assert isinstance(result.time_window_seconds, int)
        assert isinstance(result.threshold, int)

        # Verificar valores
        assert result.message_count > 0
        assert result.threshold > 0
        assert result.time_window_seconds > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
