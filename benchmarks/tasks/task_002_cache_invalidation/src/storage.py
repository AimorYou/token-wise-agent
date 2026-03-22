"""Simple in-memory key-value storage."""


class Storage:
    """Persistent (in-memory) key-value store."""

    def __init__(self):
        self._data: dict = {}

    def get(self, key: str):
        """Return the value for *key*, or ``None`` if missing."""
        return self._data.get(key)

    def set(self, key: str, value) -> None:
        """Create or update *key* with *value*."""
        self._data[key] = value

    def delete(self, key: str) -> None:
        """Remove *key* if it exists."""
        self._data.pop(key, None)

    def keys(self):
        return list(self._data.keys())
