"""Configuration file loader.

Currently supports YAML files only.  JSON support is requested but not yet
implemented — the stub raises ``ValueError`` for ``.json`` files.
"""

import os

import yaml

from .utils import merge_defaults, validate_config


def load_config(path: str) -> dict:
    """Load, validate, and return a configuration dictionary.

    Parameters
    ----------
    path : str
        Path to a configuration file.  Supported extensions:
        ``.yaml``, ``.yml``, ``.json``.

    Returns
    -------
    dict
        Parsed and validated configuration with defaults applied.

    Raises
    ------
    ValueError
        If the file extension is unsupported.
    FileNotFoundError
        If *path* does not exist.
    """
    ext = os.path.splitext(path)[1].lower()

    if ext in (".yaml", ".yml"):
        with open(path, "r") as fh:
            raw = yaml.safe_load(fh) or {}
    elif ext == ".json":
        # TODO: implement JSON loading
        raise ValueError(f"JSON config loading is not implemented yet: {path}")
    else:
        raise ValueError(f"Unsupported config format: {ext}")

    config = merge_defaults(raw)
    validate_config(config)
    return config
