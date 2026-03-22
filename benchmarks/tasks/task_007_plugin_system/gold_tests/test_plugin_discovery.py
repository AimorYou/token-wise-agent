"""Tests for the plugin discovery and registration system."""

import os

import pytest

from src.plugin_registry import clear_registry, get_plugin, list_plugins
from src.plugin_loader import discover_plugins
from src.app import App


PLUGINS_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "plugins")


@pytest.fixture(autouse=True)
def _clean_registry():
    """Reset the global registry before each test."""
    clear_registry()
    yield
    clear_registry()


# ------------------------------------------------------------------ discovery
class TestDiscovery:
    def test_discovers_all_plugins(self):
        """Both example_plugin and math_plugin must be discovered."""
        imported = discover_plugins(PLUGINS_DIR)
        assert "example_plugin" in imported
        assert "math_plugin" in imported

    def test_list_plugins_after_discovery(self):
        discover_plugins(PLUGINS_DIR)
        names = list_plugins()
        assert "greet" in names
        assert "math" in names

    def test_ignores_init_file(self):
        imported = discover_plugins(PLUGINS_DIR)
        assert "__init__" not in imported


# ------------------------------------------------------------------ registry
class TestRegistry:
    def test_get_plugin_returns_instance(self):
        """get_plugin must return a usable instance, not a class."""
        discover_plugins(PLUGINS_DIR)
        plugin = get_plugin("greet")
        assert not isinstance(plugin, type), (
            "get_plugin should return an instance, not a class"
        )

    def test_greet_plugin_execute(self):
        discover_plugins(PLUGINS_DIR)
        plugin = get_plugin("greet")
        assert plugin.execute(name="Alice") == "Hello, Alice!"

    def test_math_plugin_execute(self):
        discover_plugins(PLUGINS_DIR)
        plugin = get_plugin("math")
        assert plugin.execute(operation="add", a=2, b=3) == 5
        assert plugin.execute(operation="mul", a=4, b=5) == 20

    def test_unknown_plugin_returns_none(self):
        discover_plugins(PLUGINS_DIR)
        assert get_plugin("nonexistent") is None


# ------------------------------------------------------------------ app
class TestApp:
    def test_app_discovers_all(self):
        app = App(plugin_dir=PLUGINS_DIR)
        assert "greet" in app.available_plugins
        assert "math" in app.available_plugins

    def test_app_run_greet(self):
        app = App(plugin_dir=PLUGINS_DIR)
        result = app.run_plugin("greet", name="Bot")
        assert result == "Hello, Bot!"

    def test_app_run_math(self):
        app = App(plugin_dir=PLUGINS_DIR)
        result = app.run_plugin("math", operation="sub", a=10, b=4)
        assert result == 6

    def test_app_missing_plugin_raises(self):
        app = App(plugin_dir=PLUGINS_DIR)
        with pytest.raises(KeyError, match="not found"):
            app.run_plugin("doesnotexist")
