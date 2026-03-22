"""Handler registry with priority support."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Tuple


class HandlerRegistry:
    """Stores event handlers grouped by event name with priorities.

    Handlers are sorted by priority (lower = runs first).
    """

    def __init__(self):
        # {event_name: [(priority, handler), ...]}
        self._handlers: Dict[str, List[Tuple[int, Callable]]] = {}

    # BUG: No lock protection — iterating self._handlers[name] in
    # get_handlers while another thread mutates the list via add_handler
    # causes RuntimeError or missed handlers.

    def add_handler(
        self, event_name: str, handler: Callable, priority: int = 10
    ) -> None:
        """Register *handler* for *event_name* with given *priority*."""
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        self._handlers[event_name].append((priority, handler))
        # Re-sort so lowest priority number runs first
        self._handlers[event_name].sort(key=lambda t: t[0])

    def get_handlers(self, event_name: str) -> List[Callable]:
        """Return handlers for *event_name* in priority order."""
        pairs = self._handlers.get(event_name, [])
        # BUG: returns a live view — iteration in the caller can race
        # with concurrent add_handler that mutates the same list.
        return [h for _, h in pairs]

    def remove_handler(self, event_name: str, handler: Callable) -> bool:
        """Remove a specific handler.  Returns True if found."""
        if event_name not in self._handlers:
            return False
        before = len(self._handlers[event_name])
        self._handlers[event_name] = [
            (p, h) for p, h in self._handlers[event_name] if h is not handler
        ]
        return len(self._handlers[event_name]) < before

    def clear(self, event_name: str | None = None) -> None:
        if event_name:
            self._handlers.pop(event_name, None)
        else:
            self._handlers.clear()

    def all_event_names(self) -> list[str]:
        return list(self._handlers.keys())
