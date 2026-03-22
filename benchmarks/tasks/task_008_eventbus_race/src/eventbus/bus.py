"""Core event bus — dispatches events to registered handlers."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List

from .events import Event
from .handlers import HandlerRegistry
from .middleware import MiddlewareChain


class EventBus:
    """In-process event bus with middleware and priority support.

    Thread-safety contract (currently **broken**):
    - ``subscribe()`` and ``emit()`` SHOULD be safe to call from
      different threads concurrently, but they are NOT because neither
      the handler registry nor the middleware chain use any locking.
    """

    def __init__(self):
        self._registry = HandlerRegistry()
        self._middleware = MiddlewareChain()
        self._history: List[Event] = []

    # ---------------------------------------------------------------- public

    def subscribe(
        self,
        event_name: str,
        handler: Callable,
        priority: int = 10,
    ) -> None:
        """Register *handler* for *event_name*."""
        self._registry.add_handler(event_name, handler, priority)

    def unsubscribe(self, event_name: str, handler: Callable) -> bool:
        return self._registry.remove_handler(event_name, handler)

    def emit(self, event: Event) -> list[Any]:
        """Dispatch *event* through middleware → handlers.

        Returns a list of handler return values.
        """
        self._history.append(event)
        handlers = self._registry.get_handlers(event.name)

        def _run_handlers(evt: Event) -> list[Any]:
            results = []
            # BUG: iterating `handlers` which is built from a live list —
            # a concurrent subscribe() can cause the underlying list to
            # change mid-iteration.
            for h in handlers:
                results.append(h(evt))
            return results

        return self._middleware.execute(event, _run_handlers)

    async def emit_async(self, event: Event) -> list[Any]:
        """Async version of emit — awaits async handlers."""
        self._history.append(event)
        handlers = self._registry.get_handlers(event.name)

        async def _run_handlers(evt: Event) -> list[Any]:
            results = []
            for h in handlers:
                if asyncio.iscoroutinefunction(h):
                    results.append(await h(evt))
                else:
                    results.append(h(evt))
            return results

        return await _run_handlers(event)

    def use(self, middleware: Callable) -> None:
        """Add a middleware to the processing chain."""
        self._middleware.add(middleware)

    @property
    def history(self) -> list[Event]:
        return list(self._history)

    def clear(self) -> None:
        """Reset bus state."""
        self._registry.clear()
        self._history.clear()
