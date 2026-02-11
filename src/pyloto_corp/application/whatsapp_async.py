"""Helpers de fluxo assíncrono do WhatsApp (webhook → fila → outbound)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import HTTPException, Request, status

from pyloto_corp.adapters.whatsapp.models import OutboundMessageRequest
from pyloto_corp.adapters.whatsapp.normalizer import extract_messages
from pyloto_corp.adapters.whatsapp.outbound import WhatsAppOutboundClient
from pyloto_corp.ai.orchestrator import AIOrchestrator
from pyloto_corp.config.settings import Settings
from pyloto_corp.domain.outbound_dedup import OutboundDedupeStore
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
    tasks_dispatcher: Any,
    orchestrator: AIOrchestrator,
) -> dict[str, int | str]:
    """Processa payload inbound e enfileira mensagens outbound via Cloud Tasks."""
    logger.info(
        "handle_inbound_task_started",
        extra={
            "inbound_event_id": inbound_event_id,
            "correlation_id": correlation_id,
        },
    )

    messages = extract_messages(payload)
    logger.info(
        "messages_extracted",
        extra={
            "count": len(messages),
            "inbound_event_id": inbound_event_id,
        },
    )

    deduped = 0
    enqueued = 0
    skipped = 0
    outbound_tasks: list[str] = []

    for idx, msg in enumerate(messages):
        logger.info(
            "processing_message",
            extra={
                "index": idx,
                "message_id_prefix": msg.message_id[:8] if msg.message_id else None,
                "has_from": bool(msg.from_number),
                "has_text": bool(msg.text),
            },
        )

        if not msg.from_number or not msg.text:
            logger.warning(
                "message_skipped_missing_fields",
                extra={
                    "index": idx,
                    "has_from": bool(msg.from_number),
                    "has_text": bool(msg.text),
                },
            )
            skipped += 1
            continue

        recipient = msg.from_number
        if recipient and not recipient.startswith("+"):
            recipient = f"+{recipient}"

        logger.info(
            "calling_orchestrator",
            extra={
                "message_id_prefix": msg.message_id[:8],
                "text_preview": msg.text[:30] if msg.text else None,
            },
        )

        response = orchestrator.process_message(message=msg)

        logger.info(
            "orchestrator_response",
            extra={
                "message_id_prefix": msg.message_id[:8],
                "has_reply": bool(response.reply_text),
                "intent": str(response.intent) if response.intent else None,
                "outcome": str(response.outcome) if response.outcome else None,
                "reply_preview": response.reply_text[:50] if response.reply_text else None,
            },
        )

        if not response.reply_text:
            logger.warning(
                "message_skipped_no_reply",
                extra={
                    "message_id_prefix": msg.message_id[:8],
                    "intent": str(response.intent) if response.intent else None,
                    "outcome": str(response.outcome) if response.outcome else None,
                },
            )
            skipped += 1
            continue

        outbound_job = {
            "to": recipient,
            "message_type": "text",
            "text": response.reply_text,
            "idempotency_key": msg.message_id,
            "correlation_id": correlation_id,
            "inbound_event_id": inbound_event_id,
        }

        logger.info(
            "outbound_job_prepared",
            extra={
                "recipient_has_plus": recipient.startswith("+") if recipient else False,
                "recipient_len": len(recipient) if recipient else 0,
                "idempotency_key_prefix": msg.message_id[:8],
                "text_len": len(response.reply_text) if response.reply_text else 0,
            },
        )

        try:
            logger.info(
                "enqueuing_outbound",
                extra={
                    "idempotency_key_prefix": msg.message_id[:8],
                },
            )
            task_meta = await tasks_dispatcher.enqueue_outbound(outbound_job)
            outbound_tasks.append(task_meta.name)
            enqueued += 1
            logger.info(
                "outbound_enqueued",
                extra={
                    "task_name": task_meta.name,
                    "idempotency_key_prefix": msg.message_id[:8],
                },
            )
        except Exception as exc:
            logger.error(
                "enqueue_outbound_failed",
                extra={
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "idempotency_key_prefix": msg.message_id[:8],
                },
                exc_info=True,
            )
            # Falha na enfileiração: tratamos como 503 (fail-closed)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="enqueue_outbound_failed",
            ) from exc

    logger.info(
        "handle_inbound_task_completed",
        extra={
            "inbound_event_id": inbound_event_id,
            "processed": enqueued,
            "skipped": skipped,
            "deduped": deduped,
        },
    )

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
    except Exception as exc:
        # Tratamos HttpError-like exceptions generically sem importar infra types
        if getattr(exc, "is_retryable", False):
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
        logger.error(
            "whatsapp_send_failed",
            extra={
                "error_code": response.error_code,
                "error_message": response.error_message,
            },
        )
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
