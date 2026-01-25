"""Rotas HTTP principais."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from pyloto_corp.adapters.whatsapp.signature import verify_meta_signature
from pyloto_corp.ai.orchestrator import AIOrchestrator
from pyloto_corp.api.dependencies import (
    get_dedupe_store,
    get_orchestrator,
    get_session_store,
    get_settings,
)
from pyloto_corp.application.pipeline import process_whatsapp_webhook
from pyloto_corp.config.settings import Settings
from pyloto_corp.infra.dedupe import DedupeStore
from pyloto_corp.infra.session_store import SessionStore
from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()



@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    """Healthcheck simples para Cloud Run."""

    return {"status": "ok", "service": settings.service_name, "version": settings.version}


@router.get("/webhooks/whatsapp")
def whatsapp_verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Verificação de webhook exigida pela Meta."""

    if not settings.whatsapp_verify_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="missing_verify_token",
        )

    if (hub_mode != "subscribe" or
            hub_verify_token != settings.whatsapp_verify_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="verification_failed"
        )

    return Response(content=hub_challenge or "", media_type="text/plain")


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
    dedupe_store: DedupeStore = Depends(get_dedupe_store),
    session_store: SessionStore = Depends(get_session_store),
    orchestrator: AIOrchestrator = Depends(get_orchestrator),
) -> dict[str, Any]:
    """Recebe eventos do WhatsApp (batch-safe)."""

    raw_body = await request.body()
    signature_result = verify_meta_signature(
        raw_body, request.headers, settings.whatsapp_webhook_secret
    )

    if not signature_result.valid:
        logger.warning(
            "Invalid webhook signature", extra={"reason": signature_result.error}
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_signature")

    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_json"
        ) from exc

    result = process_whatsapp_webhook(
        payload, dedupe_store, session_store, orchestrator
    )
    result.summary.signature_validated = not signature_result.skipped
    result.summary.signature_skipped = signature_result.skipped

    return {"ok": True, "result": result.summary.model_dump()}
