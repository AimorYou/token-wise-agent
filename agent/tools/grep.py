"""
GrepTool — поиск по файлам с контекстом вокруг совпадений.

Зачем это нужно:
  Агент часто ищет определение функции/класса через bash grep, получая только
  строки совпадений без контекста, и затем делает ещё один вызов для чтения
  нужного фрагмента. GrepTool возвращает совпадения сразу с N строками контекста,
  сокращая количество API-вызовов.

  Также возвращает структурированный вывод (файл + номер строки), что удобнее
  для последующего SmartReadTool или BashTool.
"""

import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from openhands.sdk.tool import Action, Observation, register_tool
from openhands.sdk.tool.tool import ToolAnnotations, ToolDefinition, ToolExecutor
from pydantic import Field

if TYPE_CHECKING:
    from openhands.sdk.conversation import LocalConversation

MAX_MATCHES = 50
MAX_OUTPUT_CHARS = 8_000
TOOL_DESCRIPTION = """\
Search for a regex pattern in files and return matches with surrounding context lines.

Returns file paths with line numbers and context, so you can immediately understand
the match without a follow-up read. This saves API calls compared to running grep
in bash and then reading the file separately.

Examples:
  - Find a function definition:  pattern="def my_func", include="*.py"
  - Find usages of a variable:   pattern="my_var", context_lines=3
  - Case-insensitive search:     pattern="TODO", ignore_case=true
"""


class GrepAction(Action):
    """Search for a regex pattern across files."""

    pattern: str = Field(description="Regular expression pattern to search for.")
    path: str = Field(
        default=".",
        description="File or directory to search in. Defaults to current directory.",
    )
    include: str | None = Field(
        default=None,
        description='Glob pattern to filter files (e.g. "*.py", "*.ts"). '
        "Only used when path is a directory.",
    )
    context_lines: int = Field(
        default=2,
        description="Number of lines to show before and after each match.",
    )
    ignore_case: bool = Field(
        default=False,
        description="Case-insensitive search.",
    )


class GrepObservation(Observation):
    """Results of a grep search."""


@dataclass
class _Match:
    file: str
    line_no: int
    lines: list[tuple[int, str]]  # (line_number, content) including context


def _iter_files(path: str, include: str | None):
    """Yield file paths under path matching include pattern."""
    import fnmatch

    if os.path.isfile(path):
        yield path
        return
    for root, dirs, files in os.walk(path):
        # Skip hidden dirs
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            if include is None or fnmatch.fnmatch(fname, include):
                yield os.path.join(root, fname)


def _search_file(
    filepath: str,
    regex: re.Pattern,
    context: int,
) -> list[_Match]:
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return []

    matches = []
    for i, line in enumerate(lines):
        if regex.search(line):
            start = max(0, i - context)
            end = min(len(lines), i + context + 1)
            ctx = [(n + 1, lines[n].rstrip("\n")) for n in range(start, end)]
            matches.append(_Match(file=filepath, line_no=i + 1, lines=ctx))
    return matches


def _format_matches(matches: list[_Match], truncated: bool) -> str:
    if not matches:
        return "No matches found."

    parts = []
    prev_file = None
    prev_end = -1

    for m in matches:
        if m.file != prev_file:
            parts.append(f"\n── {m.file} ──")
            prev_file = m.file
            prev_end = -1

        first_line = m.lines[0][0]
        if prev_end != -1 and first_line > prev_end + 1:
            parts.append("  ···")

        for lineno, content in m.lines:
            marker = "▶" if lineno == m.line_no else " "
            parts.append(f"  {marker} {lineno:>5} │ {content}")

        prev_end = m.lines[-1][0]

    result = "\n".join(parts).strip()
    if truncated:
        result += f"\n\n[Results truncated at {MAX_MATCHES} matches]"
    return result


class _GrepExecutor(ToolExecutor):
    def __init__(self, working_dir: str = ".") -> None:
        self._working_dir = working_dir

    def __call__(
        self,
        action: GrepAction,
        conversation: "LocalConversation | None" = None,
    ) -> GrepObservation:
        flags = re.IGNORECASE if action.ignore_case else 0
        try:
            regex = re.compile(action.pattern, flags)
        except re.error as e:
            return GrepObservation.from_text(f"Invalid regex: {e}", is_error=True)

        search_path = action.path
        if not os.path.isabs(search_path):
            search_path = os.path.join(self._working_dir, search_path)

        all_matches: list[_Match] = []
        truncated = False
        for filepath in _iter_files(search_path, action.include):
            all_matches.extend(_search_file(filepath, regex, action.context_lines))
            if len(all_matches) >= MAX_MATCHES:
                all_matches = all_matches[:MAX_MATCHES]
                truncated = True
                break

        output = _format_matches(all_matches, truncated)
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n...[truncated]"
        return GrepObservation.from_text(output)


class GrepTool(ToolDefinition[GrepAction, GrepObservation]):
    @classmethod
    def create(cls, conv_state=None, **_) -> Sequence["GrepTool"]:
        working_dir = "."
        if conv_state is not None:
            working_dir = getattr(
                getattr(conv_state, "workspace", None), "working_dir", working_dir
            )
        return [
            cls(
                action_type=GrepAction,
                observation_type=GrepObservation,
                description=TOOL_DESCRIPTION,
                annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
                executor=_GrepExecutor(working_dir=working_dir),
            )
        ]


register_tool(GrepTool.name, GrepTool)
