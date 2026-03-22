"""Simple config schema validation."""

from __future__ import annotations

from typing import Any, Dict, List


def validate(config: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """Validate *config* against a simple schema.

    Schema format::

        {
            "key": {"type": "str", "required": True},
            "nested": {
                "type": "dict",
                "children": {
                    "port": {"type": "int", "required": True},
                }
            },
            "tags": {"type": "list"},
        }

    Returns a list of error strings (empty = valid).
    """
    errors: list[str] = []
    _validate_dict(config, schema, "", errors)
    return errors


_TYPE_MAP = {
    "str": str,
    "int": int,
    "float": (int, float),
    "bool": bool,
    "list": list,
    "dict": dict,
}


def _validate_dict(
    data: dict, schema: dict, prefix: str, errors: list[str]
) -> None:
    for key, rules in schema.items():
        path = f"{prefix}.{key}" if prefix else key
        required = rules.get("required", False)
        expected_type = rules.get("type")

        if key not in data:
            if required:
                errors.append(f"{path}: required field missing")
            continue

        value = data[key]

        if expected_type and expected_type in _TYPE_MAP:
            if not isinstance(value, _TYPE_MAP[expected_type]):
                errors.append(
                    f"{path}: expected {expected_type}, "
                    f"got {type(value).__name__}"
                )
                continue

        if expected_type == "dict" and "children" in rules:
            if isinstance(value, dict):
                _validate_dict(value, rules["children"], path, errors)
