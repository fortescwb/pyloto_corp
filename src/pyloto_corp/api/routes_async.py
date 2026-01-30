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
    get_session_store,
    get_settings,
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

    # **ENFILEIRAMENTO**: Não processa aqui, apenas enfileira
    try:
        task_id = await message_queue.enqueue(payload)
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
