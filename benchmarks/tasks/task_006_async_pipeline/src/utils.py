"""Pipeline utility helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from .processor import Record


def generate_report(records: List["Record"]) -> str:
    """Produce a simple text report from processed records.

    Format (one line per record)::

        #0: TRANSFORMED_TEXT
        #1: TRANSFORMED_TEXT
        ...

    The report is **order-sensitive** — record ``#i`` must correspond to
    the i-th input file.
    """
    lines = [f"#{r.seq}: {r.transformed}" for r in records]
    return "\n".join(lines)


def filenames_from_paths(paths: List[str]) -> List[str]:
    """Extract bare filenames from full paths."""
    import os
    return [os.path.basename(p) for p in paths]
