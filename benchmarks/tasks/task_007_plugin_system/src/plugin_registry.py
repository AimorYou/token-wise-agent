"""Global plugin registry.

Plugins register themselves via the ``@register_plugin`` decorator.
The rest of the application uses ``get_plugin()`` and ``list_plugins()``
to interact with registered plugins.
"""

from __future__ import annotations

from typing import Any, Dict, Type

_registry: Dict[str, Type] = {}


def register_plugin(name: str):
    """Class decorator that registers a plugin under *name*.

    Usage::

        @register_plugin("greet")
        class GreetPlugin:
            def execute(self, **kwargs):
                ...
    """
    def decorator(cls: Type) -> Type:
        _registry[name] = cls          # stores the **class**, not an instance
        return cls
    return decorator


def get_plugin(name: str) -> Any:
    """Return the plugin registered under *name*.

    .. note::
        BUG — returns the **class** object, not an instance.  Callers
        (including ``App.run_plugin``) expect a ready-to-use instance
        with an ``execute()`` method.
    """
    return _registry.get(name)         # ← should return cls() not cls


def list_plugins() -> list[str]:
    """Return sorted names of all registered plugins."""
    return sorted(_registry.keys())


def clear_registry() -> None:
    """Remove all registered plugins (useful for testing)."""
    _registry.clear()
