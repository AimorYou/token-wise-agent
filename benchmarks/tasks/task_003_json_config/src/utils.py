"""Configuration helper utilities."""

from typing import Any

DEFAULTS = {
    "debug": False,
    "log_level": "INFO",
    "max_retries": 3,
    "timeout": 30,
}

REQUIRED_KEYS = {"log_level", "timeout"}


def merge_defaults(config: dict) -> dict:
    """Return *config* with missing keys filled from DEFAULTS."""
    merged = dict(DEFAULTS)
    merged.update(config)
    return merged


def validate_config(config: dict) -> None:
    """Raise ``ValueError`` if required keys are missing or have wrong types."""
    for key in REQUIRED_KEYS:
        if key not in config:
            raise ValueError(f"Missing required config key: {key}")
    if not isinstance(config.get("timeout"), (int, float)):
        raise ValueError("'timeout' must be a number")
