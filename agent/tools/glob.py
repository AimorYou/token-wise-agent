"""
GlobTool — быстрый поиск файлов по glob-паттерну.

Агент указывает паттерн вида **/*.py или **/test_*.py, а инструмент
возвращает список совпавших путей, отсортированный по времени последнего
изменения (сначала новые). Результаты ограничены 100 вхождениями.
"""

import os
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from openhands.sdk.tool import Action, Observation, register_tool
from openhands.sdk.tool.tool import ToolAnnotations, ToolDefinition, ToolExecutor
from pydantic import Field

if TYPE_CHECKING:
    from openhands.sdk.conversation import LocalConversation

MAX_RESULTS = 100
TOOL_DESCRIPTION = """\
Fast file search by glob pattern. Returns matching file paths sorted by \
modification time (newest first), limited to 100 results.

Examples:
  - Find all Python files:       pattern="**/*.py"
  - Find test files:             pattern="**/test_*.py"
  - Find configs in a subtree:   pattern="src/**/*.yaml"
  - Search from a specific path: pattern="*.py", path="src/utils"
"""


class GlobAction(Action):
    """Search for files matching a glob pattern."""

    pattern: str = Field(description='Glob pattern (e.g. "**/*.py", "**/test_*.py").')
    path: str = Field(
        default=".",
        description="Directory to search in. Defaults to working directory.",
    )


class GlobObservation(Observation):
    """Results of a glob search."""


class _GlobExecutor(ToolExecutor):
    def __init__(self, working_dir: str = ".") -> None:
        self._working_dir = working_dir

    def __call__(
        self,
        action: GlobAction,
        conversation: "LocalConversation | None" = None,
    ) -> GlobObservation:
        search_dir = action.path
        if not os.path.isabs(search_dir):
            search_dir = os.path.join(self._working_dir, search_dir)

        base = Path(search_dir)
        if not base.is_dir():
            return GlobObservation.from_text(f"Directory not found: {action.path}", is_error=True)

        matches = sorted(base.glob(action.pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        # Filter to files only
        matches = [m for m in matches if m.is_file()]

        truncated = len(matches) > MAX_RESULTS
        matches = matches[:MAX_RESULTS]

        if not matches:
            return GlobObservation.from_text("No files matched.")

        # Show paths relative to working dir
        lines = []
        for m in matches:
            try:
                rel = m.relative_to(self._working_dir)
            except ValueError:
                rel = m
            lines.append(str(rel))

        output = "\n".join(lines)
        if truncated:
            output += f"\n\n[Truncated at {MAX_RESULTS} results]"
        return GlobObservation.from_text(output)


class GlobTool(ToolDefinition[GlobAction, GlobObservation]):
    @classmethod
    def create(cls, conv_state=None, **_) -> Sequence["GlobTool"]:
        working_dir = "."
        if conv_state is not None:
            working_dir = getattr(
                getattr(conv_state, "workspace", None), "working_dir", working_dir
            )
        return [
            cls(
                action_type=GlobAction,
                observation_type=GlobObservation,
                description=TOOL_DESCRIPTION,
                annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
                executor=_GlobExecutor(working_dir=working_dir),
            )
        ]


register_tool(GlobTool.name, GlobTool)
