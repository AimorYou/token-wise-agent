"""Existing tests for config_loader.

These tests cover YAML loading which works correctly.
JSON support has not been implemented yet.
"""
import os
import tempfile

import pytest
import yaml

from src.config_loader import load_config


def _write_tmp(content: str, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w") as fh:
        fh.write(content)
    return path


class TestYAMLConfig:
    def test_load_yaml(self):
        path = _write_tmp(yaml.dump({"timeout": 10, "log_level": "DEBUG"}), ".yaml")
        try:
            cfg = load_config(path)
            assert cfg["timeout"] == 10
            assert cfg["log_level"] == "DEBUG"
            assert cfg["debug"] is False  # from defaults
        finally:
            os.unlink(path)

    def test_load_yml_extension(self):
        path = _write_tmp(yaml.dump({"timeout": 5, "log_level": "WARN"}), ".yml")
        try:
            cfg = load_config(path)
            assert cfg["timeout"] == 5
        finally:
            os.unlink(path)

    def test_yaml_defaults_applied(self):
        path = _write_tmp(yaml.dump({"timeout": 30, "log_level": "INFO"}), ".yaml")
        try:
            cfg = load_config(path)
            assert cfg["max_retries"] == 3  # default value
        finally:
            os.unlink(path)


class TestUnsupportedFormat:
    def test_unsupported_extension_raises(self):
        path = _write_tmp("data", ".toml")
        try:
            with pytest.raises(ValueError, match="Unsupported"):
                load_config(path)
        finally:
            os.unlink(path)
