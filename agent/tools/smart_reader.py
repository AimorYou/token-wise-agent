"""
SmartReaderTool — читает файл с опциональным диапазоном строк и контекстом.

Возможности:
  - Чтение файла целиком или конкретного диапазона строк
  - Просмотр контекста вокруг конкретной строки (±N строк)
  - Ограничение вывода для больших файлов (MAX_OUTPUT_CHARS)
  - Автоматическое разрешение относительных путей через workspace
"""

import os
from collections.abc import Sequence
from typing import TYPE_CHECKING

from openhands.sdk.tool import Action, Observation, register_tool
from openhands.sdk.tool.tool import ToolAnnotations, ToolDefinition, ToolExecutor
from pydantic import Field

if TYPE_CHECKING:
    from openhands.sdk.conversation import LocalConversation

MAX_OUTPUT_CHARS = 10_000

TOOL_DESCRIPTION = """\
Read a file and return its contents with line numbers.

Three modes of use:
1. **Full file**: just provide `path` — reads entire file (truncated if too large).
2. **Line range**: provide `start_line` and/or `end_line` — reads only that slice.
3. **Context around a line**: provide `focus_line` and optionally `context` (default 10) \
— shows ±N lines around the target line.

Output is truncated to ~10,000 characters for large files. Use line ranges to read more.

Prefer this over `bash` + `cat` — it saves tokens by returning only what you need.
"""


class SmartReaderAction(Action):
    """Read a file, optionally limited to a line range or focused on a specific line."""

    path: str = Field(description="Relative or absolute path to the file to read.")
    start_line: int | None = Field(
        default=None,
        description="First line to read (1-indexed, inclusive). Omit to start from the beginning.",
    )
    end_line: int | None = Field(
        default=None,
        description="Last line to read (1-indexed, inclusive). Omit to read until the end.",
    )
    focus_line: int | None = Field(
        default=None,
        description="Show context around this line (1-indexed). Overrides start_line/end_line.",
    )
    context: int = Field(
        default=10,
        description="Number of lines to show before and after focus_line (default 10).",
    )


class SmartReaderObservation(Observation):
    """Concrete observation returned by SmartReaderTool."""


class _SmartReaderExecutor(ToolExecutor):
    def __call__(
        self,
        action: SmartReaderAction,
        conversation: "LocalConversation | None" = None,
    ) -> Observation:
        # Resolve relative paths against workspace
        path = action.path
        if not os.path.isabs(path) and conversation is not None:
            working_dir = getattr(getattr(conversation, "workspace", None), "working_dir", None)
            if working_dir:
                path = os.path.join(working_dir, path)

        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except FileNotFoundError:
            return SmartReaderObservation.from_text(f"File not found: {action.path}", is_error=True)
        except OSError as e:
            return SmartReaderObservation.from_text(str(e), is_error=True)

        total = len(lines)

        # Determine line range
        if action.focus_line is not None:
            center = max(1, min(action.focus_line, total))
            ctx = max(0, action.context)
            start = max(0, center - 1 - ctx)
            end = min(total, center + ctx)
        else:
            start = max(0, (action.start_line or 1) - 1)
            end = min(total, action.end_line or total)

        selected = lines[start:end]

        # Format with line numbers
        numbered = "".join(f"{start + i + 1:>6} | {line}" for i, line in enumerate(selected))

        # Truncate if too large
        truncated = False
        if len(numbered) > MAX_OUTPUT_CHARS:
            numbered = numbered[:MAX_OUTPUT_CHARS]
            truncated = True

        header = f"[{action.path}  lines {start + 1}-{end} of {total}]\n"
        result = header + numbered
        if truncated:
            result += "\n...[output truncated — use start_line/end_line to read specific sections]"

        return SmartReaderObservation.from_text(result)


class SmartReaderTool(ToolDefinition[SmartReaderAction, SmartReaderObservation]):
    @classmethod
    def create(cls, conv_state=None, **_) -> Sequence["SmartReaderTool"]:
        return [
            cls(
                action_type=SmartReaderAction,
                observation_type=SmartReaderObservation,
                description=TOOL_DESCRIPTION,
                annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False),
                executor=_SmartReaderExecutor(),
            )
        ]


register_tool(SmartReaderTool.name, SmartReaderTool)
