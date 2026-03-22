"""Asynchronous file loader.

Loads files concurrently to speed up I/O-bound pipeline stages.
"""

import asyncio
from typing import List


def _read_sync(path: str) -> str:
    """Blocking file read (used inside the event loop via short sleep)."""
    with open(path, "r") as fh:
        return fh.read().strip()


async def _load_one(path: str) -> str:
    """Read a single file, simulating variable network / disk latency."""
    content = _read_sync(path)
    # Simulate I/O latency proportional to content length so that
    # shorter files finish before longer ones.
    await asyncio.sleep(len(content) * 0.002)
    return content


async def load_files_async(paths: List[str]) -> List[str]:
    """Load all *paths* concurrently and return their contents.

    .. warning::
        BUG — results are collected via ``list.append`` inside each task
        callback, so the returned list follows **completion order**, not
        the original input order.
    """
    results: List[str] = []

    async def _worker(path: str) -> None:
        content = await _load_one(path)
        results.append(content)           # ← order depends on finish time

    tasks = [asyncio.create_task(_worker(p)) for p in paths]
    await asyncio.gather(*tasks)
    return results
