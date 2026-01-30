"""Shim de compatibilidade — reexporta SessionManager e AsyncSessionManager.

Este módulo existe para manter compatibilidade com imports existentes:
    from pyloto_corp.application.session_manager import SessionManager

O código canônico agora está em pyloto_corp.application.session.manager.
"""

from __future__ import annotations

from pyloto_corp.application.session.manager import (
    AsyncSessionManager,
    SessionManager,
)

__all__ = ["SessionManager", "AsyncSessionManager"]
