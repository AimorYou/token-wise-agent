"""Data processing stage — transforms raw file contents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class Record:
    """A processed record with a sequence number and transformed content."""
    seq: int
    original: str
    transformed: str


def transform(text: str) -> str:
    """Apply a transformation to raw text.

    For this task the transformation is: uppercase + strip whitespace.
    """
    return text.upper().strip()


def process_batch(contents: List[str]) -> List[Record]:
    """Turn a list of raw strings into sequenced Records.

    The sequence number ``seq`` is assigned based on **list position**,
    so correctness depends on the input list preserving the original
    file order.
    """
    records: List[Record] = []
    for idx, raw in enumerate(contents):
        records.append(Record(
            seq=idx,
            original=raw,
            transformed=transform(raw),
        ))
    return records
