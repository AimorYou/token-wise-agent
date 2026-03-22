import os
import tempfile

import pytest

from src.cli import main
from src.file_utils import list_supported_files


# ------------------------------------------------------------------ helpers
def _make_dir_with_files(files: dict[str, str]) -> str:
    """Create a temp directory with the given files and return its path."""
    tmpdir = tempfile.mkdtemp()
    for name, content in files.items():
        with open(os.path.join(tmpdir, name), "w") as fh:
            fh.write(content)
    return tmpdir


# ------------------------------------------------------------------ file_utils
class TestListSupportedFiles:
    def test_filters_by_extension(self):
        tmpdir = _make_dir_with_files({
            "data.txt": "hello",
            "notes.csv": "a,b",
            "image.png": "binary",
            "readme.md": "# hi",
        })
        result = list_supported_files(tmpdir)
        names = [os.path.basename(p) for p in result]
        assert sorted(names) == ["data.txt", "notes.csv"]

    def test_empty_directory(self):
        tmpdir = tempfile.mkdtemp()
        assert list_supported_files(tmpdir) == []


# ------------------------------------------------------------------ CLI single
class TestCLISingleFile:
    def test_process_single_file(self):
        tmpdir = _make_dir_with_files({"hello.txt": "world"})
        path = os.path.join(tmpdir, "hello.txt")
        result = main([path])
        assert result == "PROCESSED: world"


# ------------------------------------------------------------------ CLI batch
class TestCLIBatch:
    def test_batch_processes_directory(self):
        tmpdir = _make_dir_with_files({
            "a.txt": "alpha",
            "b.csv": "beta",
            "c.png": "gamma",   # unsupported — should be skipped
        })
        result = main(["--batch", tmpdir])
        assert isinstance(result, dict)
        assert result["a.txt"] == "PROCESSED: alpha"
        assert result["b.csv"] == "PROCESSED: beta"
        assert "c.png" not in result

    def test_batch_empty_directory(self):
        tmpdir = tempfile.mkdtemp()
        result = main(["--batch", tmpdir])
        assert result == {}

    def test_batch_flag_required_for_directory(self):
        """Without --batch, passing a directory should fail gracefully."""
        tmpdir = tempfile.mkdtemp()
        with pytest.raises((IsADirectoryError, PermissionError, FileNotFoundError)):
            main([tmpdir])
