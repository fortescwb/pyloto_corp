"""Middlewares de observabilidade."""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Retorna o correlation_id corrente (ou vazio)."""

    return _correlation_id.get()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Gera ou propaga correlation_id em cada request."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        incoming = request.headers.get("x-correlation-id")
        correlation_id = incoming or str(uuid.uuid4())
        token = _correlation_id.set(correlation_id)
        try:
            response = await call_next(request)
        finally:
            _correlation_id.reset(token)

        response.headers["x-correlation-id"] = correlation_id
        return response
