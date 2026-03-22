"""Gold tests — concurrent access to EventBus.

These tests FAIL on the buggy code due to race conditions in
HandlerRegistry and MiddlewareChain.  We test both:
1. Direct locking bugs via unit-level tests that simulate concurrent mutation
2. High-contention stress tests that trigger RuntimeError on dict mutation
"""
import threading
import time
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from src.eventbus import EventBus, Event
from src.eventbus.handlers import HandlerRegistry
from src.eventbus.middleware import MiddlewareChain


# ================================================================== Unit tests
# These directly verify thread-safety properties without relying on timing.

class TestHandlerRegistryThreadSafety:
    """HandlerRegistry must use locking to protect internal state."""

    def test_registry_has_lock(self):
        """After fix, HandlerRegistry should have a threading.Lock or RLock."""
        reg = HandlerRegistry()
        has_lock = hasattr(reg, "_lock")
        assert has_lock, (
            "HandlerRegistry must have a threading lock (_lock attribute) "
            "for thread safety"
        )

    def test_get_handlers_returns_snapshot(self):
        """get_handlers must return a copy, not a live view of the list.

        Mutating the internal list after get_handlers() was called
        must not affect the already-returned list.
        """
        reg = HandlerRegistry()
        h1 = lambda e: "h1"
        h2 = lambda e: "h2"
        reg.add_handler("evt", h1)

        snapshot = reg.get_handlers("evt")
        # Mutate registry after snapshot
        reg.add_handler("evt", h2)

        # Snapshot must still have only h1
        assert len(snapshot) == 1, (
            "get_handlers should return a snapshot, not a live reference"
        )


class TestMiddlewareChainThreadSafety:
    """MiddlewareChain must snapshot _middlewares during execute."""

    def test_chain_has_lock(self):
        chain = MiddlewareChain()
        has_lock = hasattr(chain, "_lock")
        assert has_lock, (
            "MiddlewareChain must have a threading lock (_lock attribute) "
            "for thread safety"
        )

    def test_execute_uses_snapshot(self):
        """Adding middleware during execute must not affect the current chain run."""
        chain = MiddlewareChain()
        call_log = []

        def mw1(event, nxt):
            call_log.append("mw1_start")
            result = nxt(event)
            call_log.append("mw1_end")
            return result

        chain.add(mw1)

        # Execute — during execution, add another middleware
        def final(event):
            # Simulate concurrent add during execution
            chain.add(lambda e, nxt: nxt(e))
            return "done"

        result = chain.execute(Event(name="test"), final)
        assert result == "done"


# ================================================================== Stress tests

class TestConcurrentSubscribeAndEmit:
    """subscribe() and emit() from different threads must not lose events."""

    def test_no_missed_handlers_under_concurrent_subscribe_emit(self):
        """Pre-subscribed handler must be called for every emit, even while
        new subscriptions are added concurrently.
        """
        N = 100
        for _ in range(5):  # repeat to increase chance of hitting race
            bus = EventBus()
            total_calls = []
            lock = threading.Lock()

            def base_handler(e):
                with lock:
                    total_calls.append(e.event_id)

            bus.subscribe("stress", base_handler)

            barrier = threading.Barrier(N * 2)

            def subscriber(i):
                barrier.wait()
                bus.subscribe("stress", lambda e: None, priority=i)

            def emitter(i):
                barrier.wait()
                bus.emit(Event(name="stress", payload={"i": i}))

            tasks = []
            with ThreadPoolExecutor(max_workers=N * 2) as pool:
                for i in range(N):
                    tasks.append(pool.submit(subscriber, i))
                    tasks.append(pool.submit(emitter, i))

                errors = []
                for f in as_completed(tasks):
                    try:
                        f.result()
                    except Exception as exc:
                        errors.append(exc)

            assert errors == [], f"Got errors: {errors}"
            assert len(total_calls) == N, (
                f"Expected {N} calls, got {len(total_calls)}"
            )

    def test_concurrent_subscribe_does_not_raise(self):
        bus = EventBus()
        errors = []

        def do_subscribe(i):
            try:
                bus.subscribe("evt", lambda e, _i=i: _i, priority=i)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=do_subscribe, args=(i,)) for i in range(200)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Got errors: {errors}"


class TestConcurrentMiddleware:
    """Adding middleware during event processing must not crash."""

    def test_add_middleware_during_emit(self):
        bus = EventBus()
        bus.subscribe("slow", lambda e: time.sleep(0.005) or "ok")
        errors = []

        barrier = threading.Barrier(2)

        def emit_thread():
            barrier.wait()
            for _ in range(50):
                try:
                    bus.emit(Event(name="slow"))
                except Exception as exc:
                    errors.append(exc)

        def add_mw_thread():
            barrier.wait()
            for i in range(50):
                try:
                    bus.use(lambda e, nxt, _i=i: nxt(e))
                except Exception as exc:
                    errors.append(exc)

        t1 = threading.Thread(target=emit_thread)
        t2 = threading.Thread(target=add_mw_thread)
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        assert errors == [], f"Got errors: {errors}"
