"""Deep merge of nested config dicts."""

from __future__ import annotations

import copy
from typing import Any, Dict


def deep_merge(
    base: Dict[str, Any],
    override: Dict[str, Any],
    strategy: str = "override",
) -> Dict[str, Any]:
    """Recursively merge *override* into a copy of *base*.

    Strategies for list values:
    - ``"override"`` — override list replaces base list entirely.
    - ``"append"``   — override list is appended to base list.
    - ``"merge"``    — lists are merged element-wise (dicts merged by index,
      scalars replaced).  **If override list is longer, extra items should be
      appended.**

    Returns a new dict (neither input is mutated).
    """
    result = copy.deepcopy(base)
    _merge_into(result, override, strategy)
    return result


def _merge_into(target: dict, source: dict, strategy: str) -> None:
    for key, src_val in source.items():
        if key not in target:
            target[key] = copy.deepcopy(src_val)
            continue

        tgt_val = target[key]

        # Both dicts → recurse
        if isinstance(tgt_val, dict) and isinstance(src_val, dict):
            _merge_into(tgt_val, src_val, strategy)
            continue

        # Both lists → apply list strategy
        if isinstance(tgt_val, list) and isinstance(src_val, list):
            target[key] = _merge_lists(tgt_val, src_val, strategy)
            continue

        # Scalar / type mismatch → override wins
        target[key] = copy.deepcopy(src_val)


def _merge_lists(base: list, override: list, strategy: str) -> list:
    if strategy == "override":
        return copy.deepcopy(override)

    if strategy == "append":
        return copy.deepcopy(base) + copy.deepcopy(override)

    # strategy == "merge"  — element-wise
    merged: list = []
    # BUG: only iterates up to min(len(base), len(override)) — if
    # override is longer than base, the extra items are silently dropped.
    for i in range(min(len(base), len(override))):
        b, o = base[i], override[i]
        if isinstance(b, dict) and isinstance(o, dict):
            m = copy.deepcopy(b)
            _merge_into(m, o, strategy)
            merged.append(m)
        else:
            merged.append(copy.deepcopy(o))
    # BUG: should append remaining items from the longer list, but doesn't.
    return merged
