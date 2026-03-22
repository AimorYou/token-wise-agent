"""Minimal application that uses the config loader."""

from .config_loader import load_config


class App:
    """Application skeleton that loads configuration on init."""

    def __init__(self, config_path: str):
        self.config = load_config(config_path)

    @property
    def is_debug(self) -> bool:
        return self.config.get("debug", False)

    @property
    def log_level(self) -> str:
        return self.config["log_level"]
