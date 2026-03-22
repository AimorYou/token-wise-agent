"""Existing tests for EventBus — single-threaded functionality.

All tests here pass on the current (buggy) code because they do
not exercise concurrent access.
"""
import asyncio

import pytest

from src.eventbus import EventBus, Event, PriorityEvent
from src.eventbus import LoggingMiddleware, RetryMiddleware, TimeoutMiddleware
from src.eventbus.serialization import serialize_event, deserialize_event


# ------------------------------------------------------------------ basic

class TestBasicEmit:
    def test_subscribe_and_emit(self):
        bus = EventBus()
        results = []
        bus.subscribe("ping", lambda e: results.append(e.payload))
        bus.emit(Event(name="ping", payload={"msg": "hello"}))
        assert results == [{"msg": "hello"}]

    def test_multiple_handlers(self):
        bus = EventBus()
        calls = []
        bus.subscribe("x", lambda e: calls.append("a"))
        bus.subscribe("x", lambda e: calls.append("b"))
        bus.emit(Event(name="x"))
        assert calls == ["a", "b"]

    def test_no_cross_talk(self):
        bus = EventBus()
        seen = []
        bus.subscribe("a", lambda e: seen.append("a"))
        bus.emit(Event(name="b"))
        assert seen == []

    def test_emit_returns_handler_results(self):
        bus = EventBus()
        bus.subscribe("calc", lambda e: e.payload["x"] * 2)
        results = bus.emit(Event(name="calc", payload={"x": 5}))
        assert results == [10]

    def test_unsubscribe(self):
        bus = EventBus()
        handler = lambda e: "ok"
        bus.subscribe("x", handler)
        assert bus.unsubscribe("x", handler) is True
        assert bus.emit(Event(name="x")) == []


# ------------------------------------------------------------------ priority

class TestPriority:
    def test_priority_order(self):
        bus = EventBus()
        order = []
        bus.subscribe("e", lambda e: order.append("low"), priority=20)
        bus.subscribe("e", lambda e: order.append("high"), priority=1)
        bus.emit(Event(name="e"))
        assert order == ["high", "low"]


# ------------------------------------------------------------------ middleware

class TestMiddleware:
    def test_logging_middleware(self):
        bus = EventBus()
        bus.use(LoggingMiddleware())
        bus.subscribe("log", lambda e: "ok")
        result = bus.emit(Event(name="log"))
        assert result == ["ok"]

    def test_retry_middleware(self):
        bus = EventBus()
        bus.use(RetryMiddleware(max_retries=2))
        attempts = []

        def flaky(e):
            attempts.append(1)
            if len(attempts) < 3:
                raise ValueError("not yet")
            return "done"

        bus.subscribe("flaky", flaky)
        result = bus.emit(Event(name="flaky"))
        assert result == ["done"]
        assert len(attempts) == 3


# ------------------------------------------------------------------ history

class TestHistory:
    def test_history_recorded(self):
        bus = EventBus()
        bus.subscribe("x", lambda e: None)
        bus.emit(Event(name="x"))
        bus.emit(Event(name="x"))
        assert len(bus.history) == 2

    def test_clear(self):
        bus = EventBus()
        bus.subscribe("x", lambda e: None)
        bus.emit(Event(name="x"))
        bus.clear()
        assert bus.history == []


# ------------------------------------------------------------------ serialization

class TestSerialization:
    def test_roundtrip_event(self):
        e = Event(name="test", payload={"k": 1})
        raw = serialize_event(e)
        restored = deserialize_event(raw)
        assert restored.name == "test"
        assert restored.payload == {"k": 1}

    def test_roundtrip_priority_event(self):
        e = PriorityEvent(name="p", payload={}, priority=5)
        raw = serialize_event(e)
        restored = deserialize_event(raw)
        assert isinstance(restored, PriorityEvent)
        assert restored.priority == 5


# ------------------------------------------------------------------ async

class TestAsyncEmit:
    def test_async_handler(self):
        bus = EventBus()
        calls = []

        async def handler(e):
            calls.append(e.name)
            return "async_ok"

        bus.subscribe("async", handler)
        results = asyncio.run(bus.emit_async(Event(name="async")))
        assert results == ["async_ok"]
        assert calls == ["async"]
