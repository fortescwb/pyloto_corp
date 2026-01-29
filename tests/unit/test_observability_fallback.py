"""Testes para M2 + L1: correlation-id e fallback logging."""

from __future__ import annotations

import logging

import pytest

from pyloto_corp.observability.logging import log_fallback
from pyloto_corp.observability.middleware import _correlation_id, get_correlation_id


class TestLogFallback:
    """Testa log_fallback helper (L1: fallback em INFO)."""

    def test_log_fallback_basic(self, caplog):
        """log_fallback deve logar em nivel INFO com fallback_used=True."""
        logger = logging.getLogger("test")

        with caplog.at_level(logging.INFO):
            log_fallback(logger, "event_detection")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelno == logging.INFO
        assert "Fallback applied for event_detection" in record.message

    def test_log_fallback_with_reason(self, caplog):
        """log_fallback deve incluir reason no extra."""
        logger = logging.getLogger("test")

        with caplog.at_level(logging.INFO):
            log_fallback(logger, "response_generation", reason="api_timeout")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert hasattr(record, "reason")
        assert record.reason == "api_timeout"  # type: ignore

    def test_log_fallback_with_elapsed_ms(self, caplog):
        """log_fallback deve incluir elapsed_ms quando fornecido."""
        logger = logging.getLogger("test")

        with caplog.at_level(logging.INFO):
            log_fallback(
                logger,
                "message_type_selection",
                reason="parse_error",
                elapsed_ms=125.5,
            )

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert hasattr(record, "elapsed_ms")
        assert record.elapsed_ms == 125.5  # type: ignore

    def test_log_fallback_no_reason_no_elapsed(self, caplog):
        """log_fallback sem reason e elapsed_ms deve ter só component."""
        logger = logging.getLogger("test")

        with caplog.at_level(logging.INFO):
            log_fallback(logger, "event_detection")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert hasattr(record, "component")
        assert record.component == "event_detection"  # type: ignore
        assert hasattr(record, "fallback_used")
        assert record.fallback_used is True  # type: ignore


class TestCorrelationIdContextVar:
    """Testa M2: correlation_id em contextvars (async safety)."""

    def test_correlation_id_retrieval(self):
        """get_correlation_id deve retornar valor do ContextVar."""
        # Set correlation_id
        token = _correlation_id.set("test-id-123")
        try:
            assert get_correlation_id() == "test-id-123"
        finally:
            _correlation_id.reset(token)

    def test_correlation_id_default_empty(self):
        """get_correlation_id deve retornar "" se não setado."""
        # Reset to default
        _correlation_id.set("")
        assert get_correlation_id() == ""

    @pytest.mark.asyncio
    async def test_correlation_id_in_async_context(self):
        """correlation_id deve propagar em contexto async (ContextVar inheritance)."""
        # Set in outer context
        token = _correlation_id.set("async-test-id")
        try:

            async def inner_async():
                # Deve acessar o valor do contexto pai
                return get_correlation_id()

            result = await inner_async()
            assert result == "async-test-id"
        finally:
            _correlation_id.reset(token)
