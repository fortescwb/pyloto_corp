"""Context manager and helpers for latency instrumentation."""

from __future__ import annotations

import contextlib
import time
from collections.abc import Generator

from pyloto_corp.observability.logging import get_logger

logger = get_logger(__name__)


@contextlib.contextmanager
def timed(component: str) -> Generator[None, None, None]:
    """Context manager to measure and log elapsed time per component.

    Usage:
        with timed("fsm"):
            # do FSM work

    Logs structured entry with:
        - component: str (name of the measured component)
        - elapsed_ms: float (milliseconds elapsed)
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "component_latency",
            extra={
                "component": component,
                "elapsed_ms": round(elapsed_ms, 2),
            },
        )
