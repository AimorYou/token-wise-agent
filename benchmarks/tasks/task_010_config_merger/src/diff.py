"""Compute a structured diff between two configs."""

from __future__ import annotations

import copy
from typing import Any, Dict, List

DiffEntry = Dict[str, Any]
# Each entry: {"op": "added"|"removed"|"changed", "path": str, "value": ..., "old": ...}


def compute_diff(
    old: Dict[str, Any],
    new: Dict[str, Any],
) -> List[DiffEntry]:
    """Return a list of diff entries describing changes from *old* to *new*.

    Recursively walks both dicts.  For nested dicts, produces granular
    per-key diffs at all depths.
    """
    entries: list[DiffEntry] = []
    _diff_recurse(old, new, "", entries)
    return entries


def _diff_recurse(
    old: dict,
    new: dict,
    prefix: str,
    entries: list[DiffEntry],
) -> None:
    all_keys = set(old) | set(new)
    for key in sorted(all_keys):
        path = f"{prefix}.{key}" if prefix else key
        if key not in old:
            entries.append({"op": "added", "path": path, "value": copy.deepcopy(new[key])})
        elif key not in new:
            entries.append({"op": "removed", "path": path, "old": copy.deepcopy(old[key])})
        elif old[key] != new[key]:
            if (
                isinstance(old[key], dict)
                and isinstance(new[key], dict)
                and "." not in prefix
            ):
                _diff_recurse(old[key], new[key], path, entries)
            else:
                entries.append({
                    "op": "changed",
                    "path": path,
                    "old": copy.deepcopy(old[key]),
                    "value": copy.deepcopy(new[key]),
                })
