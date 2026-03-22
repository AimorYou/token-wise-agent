import pytest
from src.service import DataService


class TestCacheInvalidation:
    """Cache must return fresh data after writes."""

    def test_get_after_set_returns_new_value(self):
        svc = DataService()
        svc.set("x", 1)
        assert svc.get("x") == 1

        svc.set("x", 2)
        assert svc.get("x") == 2, "Expected updated value after set()"

    def test_multiple_updates(self):
        svc = DataService()
        for i in range(10):
            svc.set("counter", i)
            assert svc.get("counter") == i

    def test_delete_removes_cached_entry(self):
        svc = DataService()
        svc.set("tmp", "hello")
        assert svc.get("tmp") == "hello"

        svc.delete("tmp")
        assert svc.get("tmp") is None

    def test_independent_keys_not_affected(self):
        svc = DataService()
        svc.set("a", 1)
        svc.set("b", 2)
        assert svc.get("a") == 1
        assert svc.get("b") == 2

        svc.set("a", 10)
        assert svc.get("a") == 10
        assert svc.get("b") == 2, "Updating 'a' must not affect 'b'"

    def test_cache_capacity_eviction(self):
        svc = DataService(cache_capacity=2)
        svc.set("a", 1)
        svc.set("b", 2)
        svc.set("c", 3)  # should evict 'a' from cache

        # 'a' should still be retrievable from storage
        assert svc.get("a") == 1
