"""Testes mínimos para PipelineConfig e compatibilidade."""

from pyloto_corp.application.pipeline import WhatsAppInboundPipeline
from pyloto_corp.application.pipeline_config import PipelineConfig
from pyloto_corp.infra.dedupe import InMemoryDedupeStore
from pyloto_corp.infra.session_store_memory import InMemorySessionStore


class DummyOrchestrator:
    pass


def test_pipeline_config_and_from_dependencies_equivalence() -> None:
    dedupe = InMemoryDedupeStore()
    session = InMemorySessionStore()
    orchestrator = DummyOrchestrator()

    config = PipelineConfig(
        dedupe_store=dedupe,
        session_store=session,
        orchestrator=orchestrator,
    )

    # Can construct with PipelineConfig
    p1 = WhatsAppInboundPipeline(config)
    assert p1._dedupe_store is dedupe
    assert p1._sessions is session
    assert hasattr(p1, "_dedupe_manager")

    # Can construct using compatibility shim
    p2 = WhatsAppInboundPipeline.from_dependencies(
        dedupe_store=dedupe,
        session_store=session,
        orchestrator=orchestrator,
    )
    assert p2._dedupe_store is dedupe
    assert p2._sessions is session
    assert hasattr(p2, "_dedupe_manager")
    assert p1._max_intents == p2._max_intents
