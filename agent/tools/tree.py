"""
Tree helper — renders a directory structure for auto-injection into the first agent message.
Not exposed as an agent tool; called directly from cli.py.
"""

import os

_IGNORE = {
    "__pycache__",
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
}


def _render_tree(root: str, target: str, max_depth: int) -> str:
    lines: list[str] = []
    rel_root = os.path.relpath(target, root)
    lines.append(f"{rel_root}/" if rel_root != "." else ".")
    _walk(target, "", max_depth, 0, lines)
    return "\n".join(lines)


def _walk(current: str, prefix: str, max_depth: int, depth: int, lines: list[str]) -> None:
    if depth >= max_depth:
        return
    try:
        entries = sorted(os.scandir(current), key=lambda e: (not e.is_dir(), e.name))
    except PermissionError:
        return
    entries = [e for e in entries if e.name not in _IGNORE and not e.name.startswith(".")]
    for i, entry in enumerate(entries):
        is_last = i == len(entries) - 1
        connector = "└── " if is_last else "├── "
        name = entry.name + ("/" if entry.is_dir() else "")
        lines.append(f"{prefix}{connector}{name}")
        if entry.is_dir():
            extension = "    " if is_last else "│   "
            _walk(entry.path, prefix + extension, max_depth, depth + 1, lines)
