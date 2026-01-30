from __future__ import annotations

from pyloto_corp.application.pipeline_async import PipelineAsyncV3
from pyloto_corp.application.pipeline_v2 import PipelineV2
from pyloto_corp.infra.dedupe import InMemoryDedupeStore
from pyloto_corp.infra.session_store import InMemorySessionStore


def test_pipeline_v2_from_dependencies_returns_instance():
    dedupe = InMemoryDedupeStore()
    session = InMemorySessionStore()

    p = PipelineV2.from_dependencies(dedupe, session)
    assert p is not None


def test_pipeline_async_from_dependencies_returns_instance():
    dedupe = InMemoryDedupeStore()
    session = InMemorySessionStore()

    p = PipelineAsyncV3.from_dependencies(dedupe, session)
    assert p is not None
