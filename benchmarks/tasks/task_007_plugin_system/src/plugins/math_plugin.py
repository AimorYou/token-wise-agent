"""Math plugin — basic arithmetic operations."""

from src.plugin_registry import register_plugin


@register_plugin("math")
class MathPlugin:
    """Plugin that performs simple arithmetic."""

    def execute(self, operation: str = "add", a: float = 0, b: float = 0) -> float:
        if operation == "add":
            return a + b
        elif operation == "mul":
            return a * b
        elif operation == "sub":
            return a - b
        else:
            raise ValueError(f"Unknown operation: {operation}")
