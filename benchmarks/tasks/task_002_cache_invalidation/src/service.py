"""High-level data service that combines storage and caching."""

from .storage import Storage
from .cache import LRUCache


class DataService:
    """Thin service that reads through an LRU cache backed by Storage."""

    def __init__(self, cache_capacity: int = 128):
        self._storage = Storage()
        self._cache = LRUCache(capacity=cache_capacity)

    def get(self, key: str):
        """Return the value for *key* (cache-first, then storage)."""
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        value = self._storage.get(key)
        if value is not None:
            self._cache.put(key, value)
        return value

    def set(self, key: str, value) -> None:
        """Persist *value* and invalidate the cache entry."""
        self._storage.set(key, value)
        self._cache.invalidate(key)

    def delete(self, key: str) -> None:
        """Remove *key* from both storage and cache."""
        self._storage.delete(key)
        self._cache.invalidate(key)
