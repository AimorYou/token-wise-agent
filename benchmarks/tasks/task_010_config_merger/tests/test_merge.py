"""Existing tests for confmerge — simple cases that work correctly.

These tests pass on the buggy code because they don't exercise:
- list merge with dict elements of different lengths
- diff on deeply nested (>2 levels) structures
- patch with collapsed subtree diffs
"""
import os
import tempfile

import pytest

from src.confmerge import load_config, dump_config, deep_merge, compute_diff
from src.confmerge import apply_patch, validate


# ------------------------------------------------------------------ loader

class TestLoader:
    def test_load_yaml(self, tmp_path):
        f = tmp_path / "cfg.yaml"
        f.write_text("host: localhost\nport: 8080\n")
        cfg = load_config(f)
        assert cfg["host"] == "localhost"
        assert cfg["port"] == 8080

    def test_load_json(self, tmp_path):
        f = tmp_path / "cfg.json"
        f.write_text('{"host": "localhost", "port": 8080}')
        cfg = load_config(f)
        assert cfg == {"host": "localhost", "port": 8080}

    def test_env_interpolation(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MY_HOST", "prod.example.com")
        f = tmp_path / "cfg.yaml"
        f.write_text("host: ${MY_HOST}\nport: 443\n")
        cfg = load_config(f)
        assert cfg["host"] == "prod.example.com"

    def test_env_default(self, tmp_path):
        f = tmp_path / "cfg.yaml"
        f.write_text("host: ${UNSET_VAR:fallback}\n")
        cfg = load_config(f)
        assert cfg["host"] == "fallback"

    def test_dump_and_reload_json(self, tmp_path):
        data = {"a": 1, "b": [1, 2]}
        f = tmp_path / "out.json"
        dump_config(data, f)
        assert load_config(f) == data


# ------------------------------------------------------------------ merge (simple)

class TestMergeSimple:
    def test_override_scalar(self):
        result = deep_merge({"a": 1}, {"a": 2})
        assert result == {"a": 2}

    def test_add_new_key(self):
        result = deep_merge({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}

    def test_nested_dict_merge(self):
        base = {"db": {"host": "localhost", "port": 3306}}
        over = {"db": {"port": 5432}}
        result = deep_merge(base, over)
        assert result == {"db": {"host": "localhost", "port": 5432}}

    def test_override_list_strategy(self):
        result = deep_merge({"x": [1, 2]}, {"x": [3]}, strategy="override")
        assert result == {"x": [3]}

    def test_append_list_strategy(self):
        result = deep_merge({"x": [1]}, {"x": [2, 3]}, strategy="append")
        assert result == {"x": [1, 2, 3]}

    def test_merge_list_same_length_scalars(self):
        result = deep_merge({"x": [1, 2]}, {"x": [10, 20]}, strategy="merge")
        assert result == {"x": [10, 20]}

    def test_does_not_mutate_inputs(self):
        base = {"a": {"b": 1}}
        over = {"a": {"c": 2}}
        deep_merge(base, over)
        assert base == {"a": {"b": 1}}
        assert over == {"a": {"c": 2}}


# ------------------------------------------------------------------ diff (shallow)

class TestDiffShallow:
    def test_no_changes(self):
        assert compute_diff({"a": 1}, {"a": 1}) == []

    def test_added_key(self):
        diff = compute_diff({}, {"a": 1})
        assert len(diff) == 1
        assert diff[0]["op"] == "added"
        assert diff[0]["path"] == "a"

    def test_removed_key(self):
        diff = compute_diff({"a": 1}, {})
        assert len(diff) == 1
        assert diff[0]["op"] == "removed"

    def test_changed_value(self):
        diff = compute_diff({"a": 1}, {"a": 2})
        assert diff[0]["op"] == "changed"
        assert diff[0]["old"] == 1
        assert diff[0]["value"] == 2

    def test_nested_one_level(self):
        """Diff at depth=1 works correctly."""
        old = {"db": {"host": "old", "port": 3306}}
        new = {"db": {"host": "new", "port": 3306}}
        diff = compute_diff(old, new)
        # Should have one granular change: db.host
        paths = [e["path"] for e in diff]
        assert "db.host" in paths
        assert len(diff) == 1


# ------------------------------------------------------------------ patch (shallow)

class TestPatchShallow:
    def test_apply_added(self):
        diff = [{"op": "added", "path": "new_key", "value": 42}]
        result = apply_patch({"a": 1}, diff)
        assert result == {"a": 1, "new_key": 42}

    def test_apply_removed(self):
        diff = [{"op": "removed", "path": "a", "old": 1}]
        result = apply_patch({"a": 1, "b": 2}, diff)
        assert result == {"b": 2}

    def test_apply_changed(self):
        diff = [{"op": "changed", "path": "a", "old": 1, "value": 99}]
        result = apply_patch({"a": 1}, diff)
        assert result == {"a": 99}


# ------------------------------------------------------------------ schema

class TestSchema:
    def test_valid(self):
        cfg = {"host": "localhost", "port": 8080}
        schema = {
            "host": {"type": "str", "required": True},
            "port": {"type": "int", "required": True},
        }
        assert validate(cfg, schema) == []

    def test_missing_required(self):
        errors = validate({}, {"host": {"type": "str", "required": True}})
        assert any("required" in e for e in errors)

    def test_wrong_type(self):
        errors = validate({"port": "abc"}, {"port": {"type": "int"}})
        assert any("expected int" in e for e in errors)
