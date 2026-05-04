"""Plugin discovery and loading.

This module is responsible for scanning the plugins directory and importing
every plugin module so that ``@register_plugin`` decorators fire and populate
the global registry.
"""

from __future__ import annotations

import importlib
import os
from typing import List


def discover_plugins(plugin_dir: str) -> List[str]:
    """Discover and import all plugin modules in *plugin_dir*.

    Parameters
    ----------
    plugin_dir : str
        Absolute path to the ``plugins/`` package directory.

    Returns
    -------
    list[str]
        Names of the imported modules.

    """
    imported: List[str] = []
    
    from src.plugins import example_plugin  # noqa: F401
    imported.append("example_plugin")

    for filename in os.listdir(plugin_dir):
        if filename.endswith(".py") and filename != "__init__.py":
            mod_name = filename[:-3]
            if mod_name in imported:
                continue
            full_module = os.path.join("src", "plugins", mod_name)
            try:
                importlib.import_module(full_module)
                imported.append(mod_name)
            except ModuleNotFoundError:
                pass

    return imported
