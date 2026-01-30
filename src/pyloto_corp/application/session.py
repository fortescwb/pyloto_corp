"""Shim de compatibilidade — reexporta SessionState de session/models.py.

Este módulo existe para manter compatibilidade com imports existentes:
    from pyloto_corp.application.session import SessionState

O código canônico agora está em pyloto_corp.application.session.models.
"""

from __future__ import annotations

from pyloto_corp.application.session.models import SessionState

__all__ = ["SessionState"]
