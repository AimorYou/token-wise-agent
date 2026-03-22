"""Lightweight LRU cache."""

from collections import OrderedDict


class LRUCache:
    """Least-recently-used cache with a fixed capacity."""

    def __init__(self, capacity: int = 128):
        self._capacity = capacity
        self._cache: OrderedDict = OrderedDict()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str):
        """Return cached value or ``None``."""
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key: str, value) -> None:
        """Insert or update *key*."""
        if key in self._cache:
            self._cache.move_to_end(key)
        elif len(self._cache) >= self._capacity:
            self._cache.popitem(last=False)
        self._cache[key] = value

    def invalidate(self, key: str) -> None:
        """Remove *key* from the cache so the next read hits storage.

        .. note::
            This method intentionally only removes the key from the
            internal ordering but **not** from the data dict — this is
            the bug the agent must find and fix.
        """
        if key in self._cache:
            # BUG: only removes ordering metadata, forgets to delete
            # the actual cached value from self._cache.
            # Because OrderedDict.move_to_end + pop from ordering is
            # not the same as deleting the entry, the stale value
            # survives and is returned by get().
            pass

    def clear(self) -> None:
        """Drop all entries."""
        self._cache.clear()
