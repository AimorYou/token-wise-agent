"""Middleware chain for event processing."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, List

from .events import Event

logger = logging.getLogger(__name__)


class MiddlewareChain:
    """Ordered chain of middleware functions.

    Each middleware receives ``(event, next_fn)`` and must call
    ``next_fn(event)`` to continue the chain (or skip it to short-circuit).
    """

    def __init__(self):
        # BUG: No lock — adding middleware while another thread is
        # iterating _middlewares in execute() causes IndexError or
        # skipped middleware.
        self._middlewares: List[Callable] = []

    def add(self, middleware: Callable) -> None:
        """Append *middleware* to the chain."""
        self._middlewares.append(middleware)

    def execute(self, event: Event, final: Callable) -> Any:
        """Run the chain ending with *final*.

        Builds a nested call: mw0(event, mw1(event, mw2(event, final)))
        """
        chain = final
        # BUG: iterating self._middlewares without a snapshot — if
        # another thread calls add() during this loop, length can change
        # and we get IndexError or skip newly-added middleware.
        for mw in reversed(self._middlewares):
            prev = chain
            chain = lambda evt, _mw=mw, _next=prev: _mw(evt, _next)
        return chain(event)


# ------------------------------------------------------------------ built-in middleware

class LoggingMiddleware:
    """Logs event name before and after processing."""

    def __call__(self, event: Event, next_fn: Callable) -> Any:
        logger.info("Processing event: %s", event.name)
        result = next_fn(event)
        logger.info("Finished event: %s", event.name)
        return result


class RetryMiddleware:
    """Retries the downstream chain up to *max_retries* times on exception."""

    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def __call__(self, event: Event, next_fn: Callable) -> Any:
        last_exc = None
        for attempt in range(1 + self.max_retries):
            try:
                return next_fn(event)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Retry %d/%d for %s: %s",
                    attempt + 1,
                    self.max_retries,
                    event.name,
                    exc,
                )
        raise last_exc  # type: ignore[misc]


class TimeoutMiddleware:
    """Fails the event if processing exceeds *timeout* seconds."""

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    def __call__(self, event: Event, next_fn: Callable) -> Any:
        start = time.monotonic()
        result = next_fn(event)
        elapsed = time.monotonic() - start
        if elapsed > self.timeout:
            raise TimeoutError(
                f"Event {event.name} took {elapsed:.2f}s (limit {self.timeout}s)"
            )
        return result
