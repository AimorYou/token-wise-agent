# Bug: Async data loader breaks pipeline ordering

## Description

The data processing pipeline recently switched to an asynchronous file loader
to speed up I/O-bound reads.  However, since the change, **the pipeline
produces results in the wrong order** — the output no longer matches the order
of the input file list.

## Steps to reproduce

```python
import asyncio
from src.pipeline import run_pipeline

# Three files with different content sizes
# File order: a.txt (large), b.txt (small), c.txt (medium)
result = asyncio.run(run_pipeline(["a.txt", "b.txt", "c.txt"]))

# Expected: results correspond to a, b, c in that order
# Actual:   results arrive in unpredictable order (usually b, c, a)
```

## Expected behavior

The pipeline output **must** preserve the original input file order, even when
files are loaded concurrently.  Concurrency itself should **not** be removed —
the fix should keep parallel loading but restore deterministic ordering.

## Root cause hints

1. `loader.py` — `load_files_async()` fires concurrent tasks and collects
   results with a **shared mutable list** (`results.append(...)` inside each
   task).  Because tasks finish at different times (simulated via
   `asyncio.sleep` proportional to content length), the append order is
   non-deterministic.
2. `pipeline.py` — `run_pipeline()` calls the loader and then passes the
   result list through `processor.py` **assuming** order is preserved.
3. `processor.py` — `process_batch()` assigns sequence numbers starting
   from 0 based on the list position it receives, so a reordered input
   produces incorrect sequence numbers.
4. `utils.py` — `generate_report()` joins processed records and is
   order-sensitive.

## Tests currently failing in

`tests/test_pipeline_order.py`
