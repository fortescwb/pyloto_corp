"""Configuração de logging estruturado (JSON)."""

from __future__ import annotations

import logging

from pythonjsonlogger.json import JsonFormatter

from pyloto_corp.observability.middleware import get_correlation_id


class CorrelationIdFilter(logging.Filter):
    """Insere correlation_id e service no record de log.

    Importante: nunca adicionar payloads brutos ou PII nos logs.
    """

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self._service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        # Preserve correlation_id passed explicitly via `extra` when present.
        existing = getattr(record, "correlation_id", None)
        record.correlation_id = existing if existing else get_correlation_id()
        record.service = self._service_name
        return True


def configure_logging(level: str, service_name: str) -> None:
    """Configura logging JSON com campos padrao do serviço."""

    formatter = JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(correlation_id)s %(service)s",
        rename_fields={"levelname": "level", "name": "logger"},
    )

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationIdFilter(service_name))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]


def get_logger(name: str) -> logging.Logger:
    """Retorna logger simples; o filtro injeta service/correlation_id."""

    return logging.getLogger(name)


def log_fallback(
    logger: logging.Logger,
    component: str,
    reason: str | None = None,
    elapsed_ms: float | None = None,
) -> None:
    """Log observável de fallback usado (sem PII).

    Args:
        logger: Logger instance
        component: Nome do componente (ex: "event_detection", "response_generation")
        reason: Razão do fallback (ex: "timeout", "parse_error") — sem PII
        elapsed_ms: Tempo decorrido em ms (quando aplicável)

    Exemplo:
        log_fallback(logger, "response_generation", reason="api_timeout", elapsed_ms=5230)
    """
    extra = {
        "fallback_used": True,
        "component": component,
    }
    if reason:
        extra["reason"] = reason
    if elapsed_ms is not None:
        extra["elapsed_ms"] = elapsed_ms

    logger.info(
        f"Fallback applied for {component}",
        extra=extra,
    )
