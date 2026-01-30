"""Testes para latency instrumentation helper (L2)."""

from __future__ import annotations

import time
from unittest.mock import patch

from pyloto_corp.observability.timing import timed


class TestTimedContextManager:
    """Testa context manager timed() para medição de latência."""

    def test_timed_measures_elapsed_time(self):
        """timed() deve medir o tempo decorrido."""
        with patch("pyloto_corp.observability.timing.logger") as mock_logger:
            with timed("test_component"):
                time.sleep(0.01)  # Sleep 10ms

            # Verificar que foi logado
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args

            # Verificar que elapsed_ms foi gravado
            assert "elapsed_ms" in call_args.kwargs["extra"]
            elapsed = call_args.kwargs["extra"]["elapsed_ms"]
            assert elapsed >= 10.0  # At least 10ms

    def test_timed_logs_component_name(self):
        """timed() deve logar o nome do componente."""
        with patch("pyloto_corp.observability.timing.logger") as mock_logger:
            with timed("fsm"):
                pass

            # Verificar que component foi logado
            call_args = mock_logger.info.call_args
            assert call_args.kwargs["extra"]["component"] == "fsm"

    def test_timed_logs_on_exception(self):
        """timed() deve logar mesmo se houver exceção."""
        with patch("pyloto_corp.observability.timing.logger") as mock_logger:
            try:
                with timed("error_component"):
                    raise ValueError("test error")
            except ValueError:
                pass

            # Verificar que foi logado mesmo com exceção
            mock_logger.info.assert_called_once()

    def test_timed_elapsed_in_milliseconds(self):
        """Latência deve ser reportada em milliseconds."""
        with patch("pyloto_corp.observability.timing.logger") as mock_logger:
            with timed("perf_test"):
                time.sleep(0.05)  # Sleep 50ms

            call_args = mock_logger.info.call_args
            elapsed = call_args.kwargs["extra"]["elapsed_ms"]

            # Deve estar próximo a 50ms
            assert 45.0 <= elapsed <= 100.0

    def test_timed_different_components(self):
        """timed() deve suportar múltiplos componentes."""
        components = []

        with patch("pyloto_corp.observability.timing.logger") as mock_logger:
            mock_logger.info.side_effect = lambda msg, **kw: components.append(
                kw["extra"]["component"]
            )

            with timed("llm1"):
                pass
            with timed("llm2"):
                pass
            with timed("llm3"):
                pass

            assert components == ["llm1", "llm2", "llm3"]


class TestTimedComponentTracking:
    """Testa rastreamento de componentes comuns."""

    @staticmethod
    def _simulate_with_component(component: str, sleep_ms: float = 1.0) -> dict:
        """Helper para simular execução com componente."""
        with patch("pyloto_corp.observability.timing.logger") as mock_logger:
            with timed(component):
                time.sleep(sleep_ms / 1000)

            call_args = mock_logger.info.call_args
            return call_args.kwargs["extra"]

    def test_dedupe_component(self):
        """Component 'dedupe' deve ser rastreável."""
        result = self._simulate_with_component("dedupe")
        assert result["component"] == "dedupe"
        assert "elapsed_ms" in result

    def test_fsm_component(self):
        """Component 'fsm' deve ser rastreável."""
        result = self._simulate_with_component("fsm")
        assert result["component"] == "fsm"

    def test_llm_components(self):
        """Components 'llm1', 'llm2', 'llm3' devem ser rastreáveis."""
        for llm_num in [1, 2, 3]:
            result = self._simulate_with_component(f"llm{llm_num}")
            assert result["component"] == f"llm{llm_num}"

    def test_outbound_component(self):
        """Component 'outbound' deve ser rastreável."""
        result = self._simulate_with_component("outbound")
        assert result["component"] == "outbound"

    def test_total_component(self):
        """Component 'total' (pipeline total) deve ser rastreável."""
        result = self._simulate_with_component("total")
        assert result["component"] == "total"
