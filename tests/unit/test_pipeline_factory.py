from __future__ import annotations

from pyloto_corp.ai.orchestrator import AIOrchestrator
from pyloto_corp.application.factories.pipeline_factory import build_whatsapp_pipeline
from pyloto_corp.application.pipeline import WhatsAppInboundPipeline
from pyloto_corp.infra.dedupe import InMemoryDedupeStore
from pyloto_corp.infra.session_store import InMemorySessionStore


def test_factory_builds_pipeline_with_explicit_dependencies() -> None:
    dedupe = InMemoryDedupeStore()
    session = InMemorySessionStore()
    orchestrator = AIOrchestrator()

    pipeline = build_whatsapp_pipeline(
        dedupe_store=dedupe, session_store=session, orchestrator=orchestrator
    )

    assert isinstance(pipeline, WhatsAppInboundPipeline)


def test_factory_uses_defaults_when_not_provided() -> None:
    # Apenas garantir que não explode quando chamado sem args
    pipeline = build_whatsapp_pipeline()
    assert isinstance(pipeline, WhatsAppInboundPipeline)
