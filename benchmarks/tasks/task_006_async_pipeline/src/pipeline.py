"""End-to-end data processing pipeline.

Stages:
    1. load   — async file reading  (loader.py)
    2. process — transform + assign sequence numbers  (processor.py)
    3. report  — generate human-readable output  (utils.py)
"""

from __future__ import annotations

from typing import List

from .loader import load_files_async
from .processor import Record, process_batch
from .utils import generate_report


async def run_pipeline(paths: List[str]) -> List[Record]:
    """Execute the full pipeline and return processed records.

    The returned list would be in the same order as paths.
    """
    contents = await load_files_async(paths)
    records = process_batch(contents)
    return records


async def run_pipeline_with_report(paths: List[str]) -> str:
    """Run the pipeline and return a formatted text report."""
    records = await run_pipeline(paths)
    return generate_report(records)
