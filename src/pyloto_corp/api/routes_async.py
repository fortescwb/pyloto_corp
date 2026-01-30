"""⚠️  ROTA ALTERNATIVA (OPCIONAL) - NÃO USADA POR PADRÃO

Este arquivo contém uma implementação alternativa com desacoplamento via fila
(MessageQueue). A implementação padrão está em routes.py (processamento síncrono
integrado no webhook handler).

USO:
- Para ativar, altere em app.py: from pyloto_corp.api.routes_async import router
- Requer implementação de MessageQueue (Cloud Tasks, Pub/Sub, etc.)

VALIDAÇÕES:
- Assinatura X-Hub-Signature-256: ✓ implementada
- Token de verificação: ✓ implementada
- Erro 401 em assinatura inválida: ✓ implementada

MANUTENÇÃO:
- Manter sincronizado com routes.py para segurança
- Toda mudança em routes.py deve ser replicated aqui
- Preferir routes.py para novo código
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from pyloto_corp.adapters.whatsapp.signature import verify_meta_signature
from pyloto_corp.api.dependencies import (
    get_dedupe_store,
    get_flood_detector,
    get_message_queue,
    get_orchestrator,
    get_outbound_dedupe_store,
    get_session_store,
    get_settings,
    get_tasks_dispatcher,
)
from pyloto_corp.application.whatsapp_async import (
    compute_inbound_event_id,
    handle_inbound_task,
    handle_outbound_task,
)
from pyloto_corp.config.settings import Settings
from pyloto_corp.observability.logging import get_logger

if TYPE_CHECKING:
    from pyloto_corp.domain.abuse_detection import FloodDetector
    from pyloto_corp.infra.dedupe import DedupeStore
    from pyloto_corp.infra.message_queue import MessageQueue
    from pyloto_corp.infra.session_store import SessionStore
import traceback

logger = get_logger(__name__)
router = APIRouter()


def _extract_status_summaries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extrai resumos de status do webhook (sem PII)."""
    summaries: list[dict[str, Any]] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {})
            for status_event in value.get("statuses", []) or []:
                status_summary = {
                    "status": status_event.get("status"),
                    "errors": [],
                }
                for err in status_event.get("errors", []) or []:
                    status_summary["errors"].append(
                        {
                            "code": err.get("code"),
                            "title": err.get("title"),
                        }
                    )
                summaries.append(status_summary)
    return summaries


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    """Healthcheck para Cloud Run."""
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.version,
    }


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
async def whatsapp_webhook_async(
    request: Request,
    settings: Settings = Depends(get_settings),
    message_queue: MessageQueue = Depends(get_message_queue),
) -> dict[str, Any]:
    """Recebe webhook do WhatsApp e enfileira para processamento assíncrono.

    **DESACOPLAMENTO CRÍTICO**:
    - Aceita webhook em <100ms
    - Valida assinatura
    - Enfileira em Cloud Tasks/memory
    - Retorna 200 IMEDIATAMENTE
    - Workers processam em background

    Benefícios:
    - Evita timeout do Load Balancer (30s)
    - Permite 100+ msgs/segundo sem bloqueio
    - LLM calls não travam webhook handler
    """
    raw_body = await request.body()
    signature_result = verify_meta_signature(
        raw_body, request.headers, settings.whatsapp_webhook_secret
    )

    if not signature_result.valid:
        logger.warning("invalid_webhook_signature", extra={"reason": signature_result.error})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_signature")

    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_json") from exc

    status_summaries = _extract_status_summaries(payload)
    if status_summaries:
        logger.info(
            "webhook_status_event",
            extra={
                "count": len(status_summaries),
                "statuses": status_summaries[:3],
            },
        )

    # Obter correlation_id do contexto
    from pyloto_corp.observability.logging import get_correlation_id

    correlation_id = get_correlation_id()

    # **ENFILEIRAMENTO**: Envolver payload no formato esperado pelo handler
    task_body = {
        "payload": payload,
        "raw_body": raw_body.decode("utf-8", errors="replace") if raw_body else "",
        "correlation_id": correlation_id,
    }

    try:
        task_id = await message_queue.enqueue(task_body)
        logger.info(
            "webhook_enqueued",
            extra={
                "task_id": task_id,
                "signature_valid": not signature_result.skipped,
            },
        )
        return {
            "ok": True,
            "status": "enqueued",
            "task_id": task_id,
        }
    except Exception as e:
        traceback.print_exc()
        logger.error("enqueue_failed", extra={"error": str(e)}, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="enqueue_failed",
        ) from e


@router.post("/tasks/process")
async def process_task(
    request: Request,
    settings: Settings = Depends(get_settings),
    dedupe_store: DedupeStore = Depends(get_dedupe_store),
    session_store: SessionStore = Depends(get_session_store),
    flood_detector: FloodDetector = Depends(get_flood_detector),
    message_queue: MessageQueue = Depends(get_message_queue),
) -> dict[str, Any]:
    """Processa uma tarefa enfileirada.

    Este endpoint é chamado por Cloud Tasks (push model) ou por um worker externo.
    Retorna 200 se sucesso → Cloud Tasks reconhece e remove da fila.
    Retorna 5xx se erro → Cloud Tasks retry com exponential backoff.
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.error("failed_to_parse_task_payload", extra={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_json",
        ) from e

    # Aqui importa o pipeline assíncrono
    from pyloto_corp.application.pipeline_async import PipelineAsyncV3
    from pyloto_corp.infra.session_store_firestore_async import (
        AsyncFirestoreSessionStore,
    )

    try:
        from google.cloud import firestore

        firestore_client = firestore.Client()
        async_session_store = AsyncFirestoreSessionStore(firestore_client)
    except ImportError:
        logger.error("firestore_not_available")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="firestore_not_available",
        ) from None

    pipeline = PipelineAsyncV3(
        dedupe_store=dedupe_store,
        async_session_store=async_session_store,
        flood_detector=flood_detector,
    )

    # **PROCESSAMENTO ASSÍNCRONO**: Sem bloqueios
    summary = await pipeline.process_webhook(payload)
    summary.signature_validated = False  # Padrão: não validado em task handler
    logger.info("task_processed", extra={"result": summary.model_dump()})

    return {"ok": True, "result": summary.model_dump()}


# =============================================================================
# ENDPOINTS INTERNOS (Cloud Tasks handlers)
# =============================================================================


def require_internal_token(request: Request, settings: Settings) -> None:
    """Valida token interno obrigatório para endpoints internos."""
    token = request.headers.get(settings.internal_token_header)
    if not settings.internal_task_token:
        logger.warning("internal_token_not_configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="internal_token_not_configured",
        )
    if token != settings.internal_task_token:
        logger.warning("invalid_internal_token")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="invalid_internal_token",
        )


@router.post("/internal/process_inbound")
async def process_inbound(
    request: Request,
    settings: Settings = Depends(get_settings),
    tasks_dispatcher=Depends(get_tasks_dispatcher),
    orchestrator=Depends(get_orchestrator),
) -> dict[str, Any]:
    """Processa task inbound (chamado por Cloud Tasks).

    Este endpoint recebe o payload da mensagem, processa com o pipeline
    e enfileira a resposta outbound.
    """
    require_internal_token(request, settings)

    try:
        task_body = await request.json()
    except Exception as exc:
        logger.error("failed_to_parse_task_payload", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_json",
        ) from exc

    if not isinstance(task_body, dict) or "payload" not in task_body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_task_payload",
        )

    payload = task_body.get("payload", {})
    raw_body = task_body.get("raw_body", b"") or b""
    if isinstance(raw_body, str):
        raw_body = raw_body.encode("utf-8")
    inbound_event_id = task_body.get("inbound_event_id") or compute_inbound_event_id(
        payload, raw_body
    )
    correlation_id = task_body.get("correlation_id")
    task_name = request.headers.get("X-CloudTasks-TaskName")

    logger.info(
        "processing_inbound_task",
        extra={
            "correlation_id": correlation_id,
            "task_name": task_name,
        },
    )

    result = await handle_inbound_task(
        payload=payload,
        inbound_event_id=inbound_event_id,
        correlation_id=correlation_id,
        tasks_dispatcher=tasks_dispatcher,
        orchestrator=orchestrator,
    )
    logger.info(
        "inbound_task_processed",
        extra={
            "correlation_id": correlation_id,
            "processed": result.get("processed", 0),
            "skipped": result.get("skipped", 0),
        },
    )

    return {"ok": True, "result": result}


@router.post("/internal/process_outbound")
async def process_outbound(
    request: Request,
    settings: Settings = Depends(get_settings),
    outbound_store=Depends(get_outbound_dedupe_store),
) -> dict[str, Any]:
    """Processa task outbound (chamado por Cloud Tasks).

    Este endpoint recebe a mensagem a ser enviada e faz a chamada
    para a API do WhatsApp.
    """
    require_internal_token(request, settings)

    try:
        task_body = await request.json()
    except Exception as exc:
        logger.error("failed_to_parse_outbound_payload", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_json",
        ) from exc

    correlation_id = task_body.get("correlation_id")
    task_name = request.headers.get("X-CloudTasks-TaskName")

    logger.info(
        "processing_outbound_task",
        extra={
            "correlation_id": correlation_id,
            "task_name": task_name,
        },
    )

    result = await handle_outbound_task(task_body, settings, outbound_store)
    logger.info(
        "outbound_task_processed",
        extra={
            "correlation_id": correlation_id,
            "status": result.get("status"),
        },
    )
    return result
