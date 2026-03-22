"""Example plugin — returns a greeting."""

from src.plugin_registry import register_plugin


@register_plugin("greet")
class GreetPlugin:
    """Simple greeting plugin."""

    def execute(self, name: str = "World") -> str:
        return f"Hello, {name}!"
