"""Existing tests for the plugin system.

These tests cover registry basics and edge cases that work
despite the plugin discovery and instantiation bugs.
"""
import os

import pytest

from src.plugin_registry import clear_registry, get_plugin, list_plugins, register_plugin
from src.plugin_loader import discover_plugins


PLUGINS_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "plugins")


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


class TestRegistryBasic:
    def test_empty_registry(self):
        """Empty registry should return empty list."""
        assert list_plugins() == []

    def test_unknown_plugin_returns_none(self):
        """Requesting non-existent plugin returns None."""
        assert get_plugin("nonexistent") is None

    def test_register_and_list(self):
        """Manually registered plugins appear in list."""
        @register_plugin("dummy")
        class DummyPlugin:
            def execute(self, **kwargs):
                return "ok"
        assert "dummy" in list_plugins()


class TestDiscoveryBasic:
    def test_ignores_init_file(self):
        """__init__.py should not be treated as a plugin."""
        imported = discover_plugins(PLUGINS_DIR)
        assert "__init__" not in imported

    def test_returns_list(self):
        """discover_plugins should return a list."""
        result = discover_plugins(PLUGINS_DIR)
        assert isinstance(result, list)
