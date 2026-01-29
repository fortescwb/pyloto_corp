"""Dependências injetadas nas rotas."""

from __future__ import annotations

from fastapi import Request

from pyloto_corp.ai.orchestrator import AIOrchestrator
from pyloto_corp.config.settings import Settings
from pyloto_corp.domain.abuse_detection import FloodDetector
from pyloto_corp.domain.outbound_dedup import OutboundDedupeStore
from pyloto_corp.infra.cloud_tasks import CloudTasksDispatcher
from pyloto_corp.infra.dedupe import DedupeStore
from pyloto_corp.infra.inbound_processing_log import InboundProcessingLogStore
from pyloto_corp.infra.session_store import SessionStore


def get_settings(request: Request) -> Settings:
    """Retorna settings da aplicação."""

    return request.app.state.settings


def get_dedupe_store(request: Request) -> DedupeStore:
    """Retorna o store de dedupe ativo."""

    return request.app.state.dedupe_store


def get_orchestrator(request: Request) -> AIOrchestrator:
    """Retorna o orquestrador de IA."""

    return request.app.state.orchestrator


def get_session_store(request: Request) -> SessionStore:
    """Retorna o store de sessão ativo."""

    return request.app.state.session_store


def get_flood_detector(request: Request) -> FloodDetector:
    """Retorna o detector de flood ativo."""

    return request.app.state.flood_detector


def get_message_queue(request: Request) -> CloudTasksDispatcher:
    """Alias de compatibilidade: retorna dispatcher de tasks."""
    return request.app.state.tasks_dispatcher


def get_inbound_queue(request: Request) -> CloudTasksDispatcher:
    """Retorna dispatcher (inbound)."""
    return request.app.state.tasks_dispatcher


def get_outbound_queue(request: Request) -> CloudTasksDispatcher:
    """Retorna dispatcher (outbound)."""
    return request.app.state.tasks_dispatcher


def get_outbound_dedupe_store(request: Request) -> OutboundDedupeStore:
    """Retorna store de idempotência outbound."""
    return request.app.state.outbound_dedupe_store


def get_tasks_dispatcher(request: Request) -> CloudTasksDispatcher:
    """Retorna dispatcher de Cloud Tasks."""
    return request.app.state.tasks_dispatcher


def get_inbound_log_store(request: Request) -> InboundProcessingLogStore:
    """Retorna store de rastro de processamento inbound."""
    return request.app.state.inbound_log_store
