"""
BashTool — запускает bash-команду через subprocess (каждый вызов независим).

Отличие от OpenHands TerminalTool:
  - TerminalTool использует tmux/persistent session (состояние между вызовами сохраняется)
  - BashTool каждый раз запускает новый subprocess — проще, детерминированнее,
    удобно для коротких команд и скриптов без сохранения состояния

Применение:
  - Запуск тестов, линтеров, сборки
  - Быстрые файловые операции (ls, find, wc, diff)
  - Установка пакетов
  - Применение патчей
"""

import subprocess
from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import Field

from openhands.sdk.tool import Action, Observation, register_tool
from openhands.sdk.tool.tool import ToolAnnotations, ToolDefinition, ToolExecutor

if TYPE_CHECKING:
    from openhands.sdk.conversation import LocalConversation

MAX_OUTPUT_CHARS = 8_000
TOOL_DESCRIPTION = """\
Execute a bash command in a fresh subprocess (stateless — no session state between calls).

Use this for:
- Running tests, linters, and build tools
- File operations (ls, find, wc, diff, cp, mv)
- Applying patches
- Installing packages

For commands that need a persistent shell session (e.g. activating a virtualenv
and then running commands inside it), use the `terminal` tool instead.

Output is truncated to 8000 characters.
"""


class BashAction(Action):
    """Run a bash command in a fresh subprocess."""

    command: str = Field(description="The bash command to execute.")
    description: str = Field(
        default="",
        description="Short description of what the command does (for logging).",
    )
    timeout: int | None = Field(
        default=None,
        description="Timeout in seconds. Defaults to the tool's configured timeout.",
    )


class BashObservation(Observation):
    """Result of a bash command execution."""

    exit_code: int = Field(default=0, description="Exit code of the command.")


class _BashExecutor(ToolExecutor):
    def __init__(self, working_dir: str = ".", default_timeout: int = 120) -> None:
        self._working_dir = working_dir
        self._default_timeout = default_timeout

    def __call__(
        self,
        action: BashAction,
        conversation: "LocalConversation | None" = None,
    ) -> BashObservation:
        timeout = action.timeout or self._default_timeout
        command = action.command.replace("/testbed", self._working_dir)
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self._working_dir,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return BashObservation.from_text(
                f"Command timed out after {timeout}s.",
                is_error=True,
                exit_code=-1,
            )
        except Exception as e:
            return BashObservation.from_text(str(e), is_error=True, exit_code=-1)

        output = result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n...[truncated]"

        return BashObservation.from_text(
            output.strip() or "(no output)",
            is_error=result.returncode != 0,
            exit_code=result.returncode,
        )


class BashTool(ToolDefinition[BashAction, BashObservation]):
    @classmethod
    def create(
        cls,
        conv_state=None,
        working_dir: str = ".",
        default_timeout: int = 120,
        **_,
    ) -> Sequence["BashTool"]:
        # Use workspace working dir if available
        if conv_state is not None:
            working_dir = getattr(
                getattr(conv_state, "workspace", None), "working_dir", working_dir
            )
        return [
            cls(
                action_type=BashAction,
                observation_type=BashObservation,
                description=TOOL_DESCRIPTION,
                annotations=ToolAnnotations(
                    readOnlyHint=False,
                    destructiveHint=True,
                    openWorldHint=True,
                ),
                executor=_BashExecutor(
                    working_dir=working_dir,
                    default_timeout=default_timeout,
                ),
            )
        ]


register_tool(BashTool.name, BashTool)
