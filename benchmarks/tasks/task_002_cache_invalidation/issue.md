# Bug: LRU cache returns stale results after update

## Description

The caching logic in `cache.py` is supposed to invalidate entries when the
underlying data changes. However, after updating a value via `DataService.set()`,
the old cached result is still returned by `DataService.get()`.

## Steps to reproduce

```python
from src.service import DataService

svc = DataService()
svc.set("x", 1)
print(svc.get("x"))  # 1

svc.set("x", 2)
print(svc.get("x"))  # Expected: 2, Actual: 1 (stale cache)
```

## Expected behavior

When `storage.set(key, value)` is called through the service layer, the
corresponding cache entry should be invalidated so that subsequent reads
return the updated value.

## Notes

The bug likely involves interaction between `storage.py` and `cache.py`.
The service layer in `service.py` does attempt to invalidate the cache,
so look carefully at the invalidation logic itself.
