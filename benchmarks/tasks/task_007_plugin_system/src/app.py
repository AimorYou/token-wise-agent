"""Application that uses the plugin system.

DO NOT MODIFY this file — the agent should fix ``plugin_loader.py`` and
``plugin_registry.py`` so that this module works as-is.
"""

from __future__ import annotations

import os
from typing import Any

from .plugin_loader import discover_plugins
from .plugin_registry import get_plugin, list_plugins


class App:
    """Minimal application with plugin support."""

    def __init__(self, plugin_dir: str | None = None):
        if plugin_dir is None:
            plugin_dir = os.path.join(os.path.dirname(__file__), "plugins")
        self._plugin_dir = plugin_dir
        discover_plugins(self._plugin_dir)

    def run_plugin(self, plugin_name: str, **kwargs: Any) -> Any:
        """Look up a plugin by *plugin_name* and execute it."""
        plugin = get_plugin(plugin_name)
        if plugin is None:
            raise KeyError(f"Plugin {plugin_name!r} not found")
        return plugin.execute(**kwargs)        # expects an *instance*

    @property
    def available_plugins(self) -> list[str]:
        return list_plugins()
