from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

CircuitState = Literal["closed", "open", "half_open"]


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Configuração do circuit breaker com defaults conservadores."""

    enabled: bool = False
    fail_max: int = 5
    reset_timeout_seconds: float = 60.0
    half_open_max_calls: int = 1


class CircuitBreaker:
    """Implementação simples de circuit breaker para chamadas HTTP."""

    def __init__(
        self,
        config: CircuitBreakerConfig,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._config = config
        self._state: CircuitState = "closed"
        self._failure_count: int = 0
        self._opened_at: float | None = None
        self._half_open_calls: int = 0
        self._clock = clock or time.monotonic
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Retorna estado atual (para observabilidade e testes)."""

        return self._state

    @property
    def failure_count(self) -> int:
        """Quantidade de falhas consecutivas registradas."""

        return self._failure_count

    async def allow_request(self) -> bool:
        """Determina se a requisição pode prosseguir.

        - Se desabilitado, sempre permite.
        - Se aberto e dentro do timeout, bloqueia.
        - Após timeout, entra em half-open limitando chamadas de teste.
        """

        if not self._config.enabled:
            return True

        async with self._lock:
            if self._state == "open":
                if self._opened_at is None:
                    self._opened_at = self._clock()
                elapsed = self._clock() - self._opened_at
                if elapsed < self._config.reset_timeout_seconds:
                    return False
                self._state = "half_open"
                self._half_open_calls = 0

            if self._state == "half_open":
                if self._half_open_calls >= self._config.half_open_max_calls:
                    return False
                self._half_open_calls += 1
                return True

            return True

    async def record_success(self) -> CircuitState:
        """Reseta contador e fecha o circuito após sucesso."""

        if not self._config.enabled:
            return "closed"

        async with self._lock:
            self._reset()
            return self._state

    async def record_failure(self, is_retryable: bool) -> CircuitState:
        """Registra falha e abre circuito conforme política.

        Falhas não retentáveis resetam o contador (não devem abrir o breaker).
        """

        if not self._config.enabled:
            return "closed"

        async with self._lock:
            if not is_retryable:
                self._reset()
                return self._state

            if self._state == "half_open":
                self._trip()
                return self._state

            self._failure_count += 1
            if self._failure_count >= self._config.fail_max:
                self._trip()
            return self._state

    def _reset(self) -> None:
        self._state = "closed"
        self._failure_count = 0
        self._opened_at = None
        self._half_open_calls = 0

    def _trip(self) -> None:
        self._state = "open"
        self._opened_at = self._clock()
        self._half_open_calls = 0

