"""Load / dump config files (YAML, JSON) with env-var interpolation."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict

import yaml


_ENV_RE = re.compile(r"\$\{(\w+)(?::([^}]*))?\}")


def _interpolate(value: Any) -> Any:
    """Replace ``${VAR}`` or ``${VAR:default}`` in string values."""
    if isinstance(value, str):
        def _replacer(m: re.Match) -> str:
            var, default = m.group(1), m.group(2)
            return os.environ.get(var, default if default is not None else m.group(0))
        return _ENV_RE.sub(_replacer, value)
    if isinstance(value, dict):
        return {k: _interpolate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v) for v in value]
    return value


def load_config(path: str | Path) -> Dict[str, Any]:
    """Load YAML or JSON config and interpolate env vars."""
    p = Path(path)
    text = p.read_text()
    if p.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(text) or {}
    elif p.suffix == ".json":
        data = json.loads(text)
    else:
        raise ValueError(f"Unsupported format: {p.suffix}")
    return _interpolate(data)


def dump_config(data: Dict[str, Any], path: str | Path) -> None:
    p = Path(path)
    if p.suffix in (".yaml", ".yml"):
        p.write_text(yaml.dump(data, default_flow_style=False))
    elif p.suffix == ".json":
        p.write_text(json.dumps(data, indent=2))
    else:
        raise ValueError(f"Unsupported format: {p.suffix}")
