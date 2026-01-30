"""Package `session` — ciclo de vida e persistência de sessão.

Exports principais:
- SessionState: modelo de estado da sessão (de session/models.py)
- SessionManager: gerenciador síncrono de sessão (de session/manager.py)
- AsyncSessionManager: gerenciador assíncrono de sessão (de session/manager.py)
"""

from __future__ import annotations

from pyloto_corp.application.session.models import SessionState

__all__ = ["SessionState", "SessionManager", "AsyncSessionManager"]


def __getattr__(name: str):
    """Lazy import para managers (evita import circular)."""
    if name in ("SessionManager", "AsyncSessionManager"):
        from pyloto_corp.application.session.manager import (
            AsyncSessionManager,
            SessionManager,
        )

        return {
            "SessionManager": SessionManager,
            "AsyncSessionManager": AsyncSessionManager,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
