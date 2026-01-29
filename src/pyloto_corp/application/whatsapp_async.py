"""Helpers de fluxo assíncrono do WhatsApp (webhook → fila → outbound)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import HTTPException, Request, status

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest
from pyloto_corp.adapters.whatsapp.normalizer import extract_messages
from pyloto_corp.adapters.whatsapp.outbound import WhatsAppOutboundClient
from pyloto_corp.config.settings import Settings
from pyloto_corp.domain.outbound_dedup import OutboundDedupeStore
from pyloto_corp.infra.cloud_tasks import CloudTaskDispatchError, CloudTasksDispatcher
from pyloto_corp.infra.http import HttpError
from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)


def _safe_mark_failed(store: OutboundDedupeStore, key: str, error: str | None) -> None:
    """Marca falha sem permitir que exceções quebrem o handler."""
    try:
        store.mark_failed(key, error=error)
    except Exception as exc:  # noqa: BLE001
        logger.error("outbound_mark_failed_error", extra={"error": str(exc)})


def _safe_mark_sent(store: OutboundDedupeStore, key: str, message_id: str) -> bool:
    """Marca como enviado; retorna False em falha silenciosa."""
    try:
        return store.mark_sent(key, message_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("outbound_mark_sent_error", extra={"error": str(exc)})
        return False


def ensure_webhook_secret(settings: Settings) -> None:
    """Fail-closed quando secret está ausente em staging/prod."""
    if (settings.is_staging or settings.is_production) and not settings.whatsapp_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="missing_webhook_secret",
        )


def require_internal_token(request: Request, settings: Settings) -> None:
    """Valida token interno enviado pelo Cloud Tasks/worker."""
    expected = settings.internal_task_token
    header_name = settings.internal_token_header
    provided = request.headers.get(header_name)

    if expected and provided == expected:
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="unauthorized_internal_call",
    )


def compute_inbound_event_id(payload: dict[str, Any], raw_body: bytes) -> str:
    """Gera chave de idempotência inbound baseada no message_id ou hash."""
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", []) or []
            if messages and isinstance(messages[0], dict):
                msg_id = messages[0].get("id")
                if msg_id:
                    return msg_id

    digest = hashlib.sha256(
        raw_body or json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"payload:{digest}"


async def handle_inbound_task(
    payload: dict[str, Any],
    inbound_event_id: str,
    correlation_id: str | None,
    tasks_dispatcher: CloudTasksDispatcher,
) -> dict[str, int | str]:
    """Processa payload inbound e enfileira mensagens outbound via Cloud Tasks."""
    messages = extract_messages(payload)
    deduped = 0
    enqueued = 0
    skipped = 0
    outbound_tasks: list[str] = []

    for msg in messages:
        if not msg.from_number:
            skipped += 1
            continue

        outbound_job = {
            "to": msg.from_number,
            "message_type": "text",
            "text": "Mensagem recebida",
            "idempotency_key": msg.message_id,
            "correlation_id": correlation_id,
            "inbound_event_id": inbound_event_id,
        }
        try:
            task_meta = await tasks_dispatcher.enqueue_outbound(outbound_job)
            outbound_tasks.append(task_meta.name)
            enqueued += 1
        except CloudTaskDispatchError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="enqueue_outbound_failed",
            ) from exc

    return {
        "inbound_event_id": inbound_event_id,
        "processed": enqueued,
        "deduped": deduped,
        "skipped": skipped,
        "outbound_tasks": outbound_tasks,
    }


async def handle_outbound_task(
    task_body: dict[str, Any],
    settings: Settings,
    outbound_store: OutboundDedupeStore,
) -> dict[str, Any]:
    """Processa envio outbound com idempotência e classificação de erro."""
    correlation_id = task_body.get("correlation_id") if isinstance(task_body, dict) else None
    inbound_event_id = task_body.get("inbound_event_id") if isinstance(task_body, dict) else None

    try:
        outbound_request = OutboundMessageRequest.model_validate(task_body)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_outbound_payload"
        ) from exc

    if not outbound_request.idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="missing_idempotency_key",
        )

    try:
        dedupe_result = outbound_store.check_and_mark(
            outbound_request.idempotency_key,
            outbound_request.idempotency_key,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="outbound_dedupe_unavailable",
        ) from exc

    if dedupe_result.is_duplicate and dedupe_result.status == "sent":
        return {
            "ok": True,
            "status": dedupe_result.status,
            "idempotency_key": outbound_request.idempotency_key,
            "message_id": dedupe_result.original_message_id,
            "error": dedupe_result.error,
        }

    client = WhatsAppOutboundClient(
        api_endpoint=settings.whatsapp_api_endpoint,
        access_token=settings.whatsapp_access_token or "",
        phone_number_id=settings.whatsapp_phone_number_id or "",
    )

    try:
        response = await client.send_message(outbound_request)
    except ValueError as exc:
        _safe_mark_failed(outbound_store, outbound_request.idempotency_key, str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_outbound_config",
        ) from exc
    except HttpError as exc:
        if exc.is_retryable:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="whatsapp_retryable_error",
            ) from exc
        _safe_mark_failed(outbound_store, outbound_request.idempotency_key, str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="whatsapp_permanent_error",
        ) from exc

    if not response.success:
        _safe_mark_failed(outbound_store, outbound_request.idempotency_key, response.error_message)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="whatsapp_send_failed",
        )

    if not _safe_mark_sent(
        outbound_store,
        outbound_request.idempotency_key,
        response.message_id or outbound_request.idempotency_key,
    ):
        logger.warning(
            "outbound_mark_sent_skipped",
            extra={"idempotency_key": outbound_request.idempotency_key},
        )

    return {
        "ok": True,
        "status": "sent",
        "message_id": response.message_id,
        "idempotency_key": outbound_request.idempotency_key,
        "correlation_id": correlation_id,
        "inbound_event_id": inbound_event_id,
    }
