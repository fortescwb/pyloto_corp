"""Pipeline de processamento inbound (esqueleto)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyloto_corp.adapters.whatsapp.models import WebhookProcessingSummary
from pyloto_corp.adapters.whatsapp.normalizer import extract_messages
from pyloto_corp.ai.orchestrator import AIOrchestrator
from pyloto_corp.infra.dedupe import DedupeStore
from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class PipelineResult:
    """Resultado resumido do pipeline (sem PII)."""

    summary: WebhookProcessingSummary


def process_whatsapp_webhook(
    payload: dict[str, Any],
    dedupe_store: DedupeStore,
    orchestrator: AIOrchestrator,
) -> PipelineResult:
    """Processa o payload do webhook do WhatsApp.

    TODO: integrar sessão, intents, outcomes e outbound.
    """

    messages = extract_messages(payload)
    total_received = len(messages)
    total_deduped = 0
    total_processed = 0

    for message in messages:
        is_duplicate = dedupe_store.check_and_mark(message.message_id)
        if is_duplicate:
            total_deduped += 1
            continue

        total_processed += 1
        orchestrator.handle_messages([message])

    logger.info(
        "Webhook processed",
        extra={
            "total_received": total_received,
            "total_deduped": total_deduped,
            "total_processed": total_processed,
        },
    )

    summary = WebhookProcessingSummary(
        total_received=total_received,
        total_deduped=total_deduped,
        total_processed=total_processed,
    )

    return PipelineResult(summary=summary)
