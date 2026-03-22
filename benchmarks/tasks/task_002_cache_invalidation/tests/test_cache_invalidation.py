"""Existing tests for cache and data service.

These tests cover basic operations that work correctly even with
the invalidation bug (first set+get for each key works fine).
"""
import pytest
from src.service import DataService
from src.cache import LRUCache
from src.storage import Storage


class TestStorage:
    def test_set_and_get(self):
        s = Storage()
        s.set("key", 42)
        assert s.get("key") == 42

    def test_get_missing_returns_none(self):
        s = Storage()
        assert s.get("missing") is None

    def test_delete(self):
        s = Storage()
        s.set("key", 1)
        s.delete("key")
        assert s.get("key") is None


class TestLRUCache:
    def test_put_and_get(self):
        cache = LRUCache(capacity=10)
        cache.put("a", 1)
        assert cache.get("a") == 1

    def test_get_missing_returns_none(self):
        cache = LRUCache(capacity=10)
        assert cache.get("nonexistent") is None

    def test_clear(self):
        cache = LRUCache(capacity=10)
        cache.put("a", 1)
        cache.clear()
        assert cache.get("a") is None


class TestDataServiceBasic:
    def test_first_set_and_get(self):
        """First set+get for a key always works (not yet cached)."""
        svc = DataService()
        svc.set("x", 1)
        assert svc.get("x") == 1

    def test_get_missing_returns_none(self):
        svc = DataService()
        assert svc.get("missing") is None

    def test_independent_keys_first_write(self):
        """Multiple keys, each written once, should all be retrievable."""
        svc = DataService()
        svc.set("a", 1)
        svc.set("b", 2)
        svc.set("c", 3)
        assert svc.get("a") == 1
        assert svc.get("b") == 2
        assert svc.get("c") == 3
