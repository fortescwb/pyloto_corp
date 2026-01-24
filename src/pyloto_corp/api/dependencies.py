"""Dependências injetadas nas rotas."""

from __future__ import annotations

from fastapi import Request

from pyloto_corp.ai.orchestrator import AIOrchestrator
from pyloto_corp.config.settings import Settings
from pyloto_corp.infra.dedupe import DedupeStore


def get_settings(request: Request) -> Settings:
    """Retorna settings da aplicação."""

    return request.app.state.settings


def get_dedupe_store(request: Request) -> DedupeStore:
    """Retorna o store de dedupe ativo."""

    return request.app.state.dedupe_store


def get_orchestrator(request: Request) -> AIOrchestrator:
    """Retorna o orquestrador de IA."""

    return request.app.state.orchestrator
