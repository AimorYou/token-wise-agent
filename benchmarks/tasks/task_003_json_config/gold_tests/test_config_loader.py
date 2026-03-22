import json
import os
import tempfile

import pytest
import yaml

from src.config_loader import load_config
from src.app import App


# ------------------------------------------------------------------ helpers
def _write_tmp(content: str, suffix: str) -> str:
    """Write *content* to a temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w") as fh:
        fh.write(content)
    return path


# ------------------------------------------------------------------ YAML
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


# ------------------------------------------------------------------ JSON
class TestJSONConfig:
    def test_load_json_basic(self):
        data = {"timeout": 20, "log_level": "ERROR", "debug": True}
        path = _write_tmp(json.dumps(data), ".json")
        try:
            cfg = load_config(path)
            assert cfg["timeout"] == 20
            assert cfg["log_level"] == "ERROR"
            assert cfg["debug"] is True
        finally:
            os.unlink(path)

    def test_json_defaults_applied(self):
        """Keys not in the JSON file should be filled from defaults."""
        data = {"timeout": 60, "log_level": "INFO"}
        path = _write_tmp(json.dumps(data), ".json")
        try:
            cfg = load_config(path)
            assert cfg["max_retries"] == 3  # default
        finally:
            os.unlink(path)

    def test_json_validation_error(self):
        """timeout must be numeric — passing a string should raise."""
        data = {"timeout": "slow", "log_level": "INFO"}
        path = _write_tmp(json.dumps(data), ".json")
        try:
            with pytest.raises(ValueError, match="timeout"):
                load_config(path)
        finally:
            os.unlink(path)


# ------------------------------------------------------------------ App
class TestAppWithJSON:
    def test_app_loads_json_config(self):
        data = {"timeout": 15, "log_level": "DEBUG", "debug": True}
        path = _write_tmp(json.dumps(data), ".json")
        try:
            app = App(path)
            assert app.is_debug is True
            assert app.log_level == "DEBUG"
        finally:
            os.unlink(path)


# ------------------------------------------------------------------ Edge
class TestUnsupportedFormat:
    def test_unsupported_extension_raises(self):
        path = _write_tmp("data", ".toml")
        try:
            with pytest.raises(ValueError, match="Unsupported"):
                load_config(path)
        finally:
            os.unlink(path)
