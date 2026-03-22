"""Existing tests for CLI and file_utils.

These tests cover single-file processing and edge cases
that work correctly despite the file filtering bug.
"""
import os
import tempfile

import pytest

from src.cli import main


def _make_dir_with_files(files: dict[str, str]) -> str:
    tmpdir = tempfile.mkdtemp()
    for name, content in files.items():
        with open(os.path.join(tmpdir, name), "w") as fh:
            fh.write(content)
    return tmpdir


class TestCLISingleFile:
    def test_process_single_file(self):
        tmpdir = _make_dir_with_files({"hello.txt": "world"})
        path = os.path.join(tmpdir, "hello.txt")
        result = main([path])
        assert result == "PROCESSED: world"

    def test_process_csv_file(self):
        tmpdir = _make_dir_with_files({"data.csv": "a,b,c"})
        path = os.path.join(tmpdir, "data.csv")
        result = main([path])
        assert result == "PROCESSED: a,b,c"
