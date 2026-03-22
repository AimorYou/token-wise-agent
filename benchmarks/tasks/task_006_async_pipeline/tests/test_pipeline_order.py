"""Existing tests for async pipeline components.

These tests cover single-file cases and processor logic
that work correctly despite the ordering bug in load_files_async.
"""
import asyncio
import os
import tempfile
from typing import List

import pytest

from src.loader import load_files_async
from src.processor import process_batch, transform


def _create_files(contents: dict[str, str]) -> tuple[str, List[str]]:
    tmpdir = tempfile.mkdtemp()
    paths: List[str] = []
    for name, body in contents.items():
        p = os.path.join(tmpdir, name)
        with open(p, "w") as fh:
            fh.write(body)
        paths.append(p)
    return tmpdir, paths


class TestLoaderBasic:
    def test_single_file(self):
        """Single file — order doesn't matter."""
        _, paths = _create_files({"only.txt": "hello"})
        results = asyncio.run(load_files_async(paths))
        assert results == ["hello"]

    def test_empty_list(self):
        results = asyncio.run(load_files_async([]))
        assert results == []


class TestProcessor:
    def test_sequence_numbers(self):
        records = process_batch(["aaa", "bbb", "ccc"])
        assert [r.seq for r in records] == [0, 1, 2]

    def test_transform(self):
        assert transform("hello") == "HELLO"

    def test_process_batch_content(self):
        records = process_batch(["foo", "bar"])
        assert records[0].original == "foo"
        assert records[1].original == "bar"

    def test_transform_preserves_length(self):
        result = transform("test string")
        assert len(result) == len("test string")
