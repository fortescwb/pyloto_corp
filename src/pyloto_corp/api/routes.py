"""Rotas HTTP principais (fluxo assíncrono WhatsApp)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from pyloto_corp.adapters.whatsapp.signature import verify_meta_signature
from pyloto_corp.api.dependencies import (
    get_dedupe_store,
    get_inbound_log_store,
    get_outbound_dedupe_store,
    get_settings,
    get_tasks_dispatcher,
)
from pyloto_corp.application.whatsapp_async import (
    compute_inbound_event_id,
    ensure_webhook_secret,
    handle_inbound_task,
    handle_outbound_task,
    require_internal_token,
)
from pyloto_corp.config.settings import Settings
from pyloto_corp.infra.cloud_tasks import CloudTaskDispatchError, CloudTasksDispatcher
from pyloto_corp.infra.dedupe import DedupeError, DedupeStore
from pyloto_corp.infra.inbound_processing_log import InboundProcessingLogStore
from pyloto_corp.observability.logging import get_logger
from pyloto_corp.observability.middleware import get_correlation_id

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

    if hub_mode != "subscribe" or hub_verify_token != settings.whatsapp_verify_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="verification_failed",
        )

    return Response(content=hub_challenge or "", media_type="text/plain")


@router.post("/webhooks/whatsapp")
async def whatsapp_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
    dedupe_store: DedupeStore = Depends(get_dedupe_store),
    tasks_dispatcher: CloudTasksDispatcher = Depends(get_tasks_dispatcher),
) -> dict[str, Any]:
    """Recebe eventos do WhatsApp e apenas enfileira para processamento."""
    ensure_webhook_secret(settings)

    raw_body = await request.body()
    signature_result = verify_meta_signature(
        raw_body, request.headers, settings.whatsapp_webhook_secret
    )

    if not signature_result.valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_signature")

    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_json") from exc

    inbound_event_id = compute_inbound_event_id(payload, raw_body)
    correlation_id = get_correlation_id()
    try:
        is_new = dedupe_store.mark_if_new(inbound_event_id)
    except DedupeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "inbound_dedupe_unavailable",
                "correlation_id": correlation_id,
            },
        ) from exc

    if not is_new:
        logger.info("inbound_duplicate_skipped", extra={"inbound_event_id": inbound_event_id})
        return {
            "ok": True,
            "status": "duplicate",
            "enqueued": False,
            "result": "duplicate",
            "correlation_id": correlation_id,
            "inbound_event_id": inbound_event_id,
            "signature_validated": signature_result.valid and not signature_result.skipped,
            "signature_skipped": signature_result.skipped,
        }

    task_payload = {
        "payload": payload,
        "inbound_event_id": inbound_event_id,
        "correlation_id": correlation_id,
        "signature_skipped": signature_result.skipped,
        "signature_validated": signature_result.valid and not signature_result.skipped,
    }
    try:
        task_meta = await tasks_dispatcher.enqueue_inbound(task_payload)
    except CloudTaskDispatchError as exc:
        dedupe_store.clear(inbound_event_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="enqueue_failed",
        ) from exc

    return {
        "ok": True,
        "status": "enqueued",
        "enqueued": True,
        "result": "enqueued",
        "task_name": task_meta.name,
        "queue": task_meta.queue,
        "correlation_id": correlation_id,
        "inbound_event_id": inbound_event_id,
        "signature_validated": signature_result.valid and not signature_result.skipped,
        "signature_skipped": signature_result.skipped,
    }


def _mark_inbound_started(
    inbound_log_store: InboundProcessingLogStore,
    inbound_event_id: str,
    correlation_id: str | None,
    task_name: str | None,
) -> None:
    """Marca início de processamento inbound com log estruturado."""
    logger.info(
        "inbound_processing_started",
        extra={
            "inbound_event_id": inbound_event_id,
            "correlation_id": correlation_id,
            "task_name": task_name,
        },
    )
    try:
        inbound_log_store.mark_started(inbound_event_id, correlation_id, task_name)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "inbound_log_start_failed",
            extra={
                "inbound_event_id": inbound_event_id,
                "correlation_id": correlation_id,
                "task_name": task_name,
                "error": type(exc).__name__,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="inbound_log_unavailable",
        ) from exc


def _mark_inbound_finished(
    inbound_log_store: InboundProcessingLogStore,
    inbound_event_id: str,
    correlation_id: str | None,
    task_name: str | None,
    *,
    enqueued_outbound: bool,
    error: str | None,
) -> None:
    """Marca término de processamento inbound."""
    try:
        inbound_log_store.mark_finished(
            inbound_event_id,
            correlation_id=correlation_id,
            task_name=task_name,
            enqueued_outbound=enqueued_outbound,
            error=error,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "inbound_log_finish_failed",
            extra={
                "inbound_event_id": inbound_event_id,
                "correlation_id": correlation_id,
                "task_name": task_name,
                "error": type(exc).__name__,
            },
        )


def _log_inbound_finished(
    inbound_event_id: str,
    correlation_id: str | None,
    task_name: str | None,
    *,
    status: str,
    enqueued_outbound: bool,
) -> None:
    """Loga conclusão do processamento inbound."""
    logger.info(
        "inbound_processing_finished",
        extra={
            "inbound_event_id": inbound_event_id,
            "correlation_id": correlation_id,
            "task_name": task_name,
            "status": status,
            "enqueued_outbound": enqueued_outbound,
        },
    )


async def _run_inbound_with_rastro(
    payload: dict[str, Any],
    inbound_event_id: str,
    correlation_id: str | None,
    task_name: str | None,
    tasks_dispatcher: CloudTasksDispatcher,
    inbound_log_store: InboundProcessingLogStore,
) -> dict[str, Any]:
    """Executa worker inbound com rastro persistente."""
    _mark_inbound_started(inbound_log_store, inbound_event_id, correlation_id, task_name)

    try:
        result = await handle_inbound_task(
            payload=payload,
            inbound_event_id=inbound_event_id,
            correlation_id=correlation_id,
            tasks_dispatcher=tasks_dispatcher,
        )
        return _handle_inbound_success(
            inbound_log_store,
            inbound_event_id,
            correlation_id,
            task_name,
            result,
        )
    except Exception as exc:  # noqa: BLE001
        _handle_inbound_failure(
            inbound_log_store,
            inbound_event_id,
            correlation_id,
            task_name,
            exc,
        )
        raise


def _handle_inbound_success(
    inbound_log_store: InboundProcessingLogStore,
    inbound_event_id: str,
    correlation_id: str | None,
    task_name: str | None,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Finaliza fluxo inbound com sucesso."""
    enqueued_outbound = result.get("processed", 0) > 0
    _mark_inbound_finished(
        inbound_log_store,
        inbound_event_id,
        correlation_id,
        task_name,
        enqueued_outbound=enqueued_outbound,
        error=None,
    )
    _log_inbound_finished(
        inbound_event_id,
        correlation_id,
        task_name,
        status="success",
        enqueued_outbound=enqueued_outbound,
    )
    result["ok"] = True
    return result


def _handle_inbound_failure(
    inbound_log_store: InboundProcessingLogStore,
    inbound_event_id: str,
    correlation_id: str | None,
    task_name: str | None,
    exc: Exception,
) -> None:
    """Finaliza fluxo inbound em erro, registrando rastro."""
    error_str = type(exc).__name__
    _mark_inbound_finished(
        inbound_log_store,
        inbound_event_id,
        correlation_id,
        task_name,
        enqueued_outbound=False,
        error=error_str,
    )
    logger.error(
        "inbound_processing_failed",
        extra={
            "inbound_event_id": inbound_event_id,
            "correlation_id": correlation_id,
            "task_name": task_name,
            "error": error_str,
        },
    )
    _log_inbound_finished(
        inbound_event_id,
        correlation_id,
        task_name,
        status="error",
        enqueued_outbound=False,
    )


@router.post("/internal/process_inbound")
async def process_inbound(
    request: Request,
    settings: Settings = Depends(get_settings),
    tasks_dispatcher: CloudTasksDispatcher = Depends(get_tasks_dispatcher),
    inbound_log_store: InboundProcessingLogStore = Depends(get_inbound_log_store),
) -> dict[str, Any]:
    """Processa task inbound e enfileira outbound."""
    require_internal_token(request, settings)

    try:
        task_body = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_json") from exc

    if not isinstance(task_body, dict) or "payload" not in task_body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_task_payload")

    payload = task_body.get("payload", {})
    raw_body = task_body.get("raw_body", b"") or b""
    inbound_event_id = task_body.get("inbound_event_id") or compute_inbound_event_id(
        payload, raw_body
    )
    correlation_id = task_body.get("correlation_id") or get_correlation_id()
    task_name = request.headers.get("X-CloudTasks-TaskName")

    return await _run_inbound_with_rastro(
        payload=payload,
        inbound_event_id=inbound_event_id,
        correlation_id=correlation_id,
        task_name=task_name,
        tasks_dispatcher=tasks_dispatcher,
        inbound_log_store=inbound_log_store,
    )


@router.post("/internal/process_outbound")
async def process_outbound(
    request: Request,
    settings: Settings = Depends(get_settings),
    outbound_store=Depends(get_outbound_dedupe_store),
) -> dict[str, Any]:
    """Processa task outbound e envia para Meta API."""
    require_internal_token(request, settings)

    try:
        task_body = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_json") from exc

    result = await handle_outbound_task(task_body, settings, outbound_store)
    return result
