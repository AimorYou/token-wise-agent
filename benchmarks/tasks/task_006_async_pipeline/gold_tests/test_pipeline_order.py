"""Tests for the async pipeline — output order must match input order."""

import asyncio
import os
import tempfile
from typing import List

import pytest

from src.loader import load_files_async
from src.processor import process_batch, transform
from src.pipeline import run_pipeline, run_pipeline_with_report
from src.utils import generate_report


# ------------------------------------------------------------------ helpers
def _create_files(contents: dict[str, str]) -> tuple[str, List[str]]:
    """Write temp files and return (tmpdir, list_of_paths_in_key_order)."""
    tmpdir = tempfile.mkdtemp()
    paths: List[str] = []
    for name, body in contents.items():
        p = os.path.join(tmpdir, name)
        with open(p, "w") as fh:
            fh.write(body)
        paths.append(p)
    return tmpdir, paths


# ------------------------------------------------------------------ loader
class TestLoaderOrder:
    """load_files_async must return contents in the same order as input paths."""

    def test_order_preserved_different_sizes(self):
        """Files of very different sizes must still come back in input order.

        File 'a' is long  (high simulated latency → finishes last).
        File 'b' is short (low latency → finishes first).
        File 'c' is medium.
        """
        _, paths = _create_files({
            "a.txt": "A" * 200,    # long  → slow
            "b.txt": "B" * 5,      # short → fast
            "c.txt": "C" * 50,     # medium
        })
        results = asyncio.run(load_files_async(paths))
        assert results[0] == "A" * 200
        assert results[1] == "B" * 5
        assert results[2] == "C" * 50

    def test_single_file(self):
        _, paths = _create_files({"only.txt": "hello"})
        results = asyncio.run(load_files_async(paths))
        assert results == ["hello"]

    def test_empty_list(self):
        results = asyncio.run(load_files_async([]))
        assert results == []


# ------------------------------------------------------------------ processor
class TestProcessor:
    def test_sequence_numbers(self):
        records = process_batch(["aaa", "bbb", "ccc"])
        assert [r.seq for r in records] == [0, 1, 2]

    def test_transform(self):
        assert transform("hello") == "HELLO"


# ------------------------------------------------------------------ pipeline
class TestPipeline:
    def test_pipeline_preserves_order(self):
        _, paths = _create_files({
            "first.txt": "F" * 200,
            "second.txt": "S" * 5,
            "third.txt": "T" * 80,
        })
        records = asyncio.run(run_pipeline(paths))

        assert records[0].seq == 0
        assert records[0].original == "F" * 200
        assert records[1].seq == 1
        assert records[1].original == "S" * 5
        assert records[2].seq == 2
        assert records[2].original == "T" * 80

    def test_report_order(self):
        _, paths = _create_files({
            "x.txt": "X" * 150,
            "y.txt": "Y" * 10,
        })
        report = asyncio.run(run_pipeline_with_report(paths))
        lines = report.strip().split("\n")
        assert lines[0].startswith("#0:")
        assert "X" * 150 in lines[0]
        assert lines[1].startswith("#1:")
        assert "Y" * 10 in lines[1]

    def test_pipeline_five_files(self):
        """Larger batch — each file has drastically different size."""
        contents = {
            f"f{i}.txt": chr(65 + i) * length
            for i, length in enumerate([300, 10, 200, 5, 100])
        }
        _, paths = _create_files(contents)
        records = asyncio.run(run_pipeline(paths))
        for idx, rec in enumerate(records):
            assert rec.seq == idx, f"Record {idx} has wrong seq={rec.seq}"
        # Verify actual content matches original order
        expected_lengths = [300, 10, 200, 5, 100]
        for idx, rec in enumerate(records):
            assert len(rec.original) == expected_lengths[idx]
