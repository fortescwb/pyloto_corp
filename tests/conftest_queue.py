"""Conftest para testes de fila de mensagens (sem dependência do app)."""

import pytest


@pytest.fixture
def event_loop_policy():
    """Fixture para controlar event loop."""
    return None
