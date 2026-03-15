"""
SubmitTool — агент вызывает этот инструмент, когда считает, что исправил баг.

Записывает SUBMISSION.json в рабочую директорию с описанием того, что было сделано.
Бенчмарк-раннер проверяет наличие этого файла как сигнал завершения.

После вызова submit conversation loop останавливается (execution_status = FINISHED).
"""

import json
import os
from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import Field

from openhands.sdk.tool import Action, Observation, register_tool
from openhands.sdk.tool.tool import ToolAnnotations, ToolDefinition, ToolExecutor

if TYPE_CHECKING:
    from openhands.sdk.conversation import LocalConversation

TOOL_DESCRIPTION = """\
Submit your solution when you have finished fixing the bug.

Call this tool ONCE when you are confident that the bug described in the issue
has been fixed. Provide a short explanation of what you changed and why.

This tool stops the agent — no further actions will be executed after submission.
"""


class SubmitAction(Action):
    """Signal that the fix is complete."""

    explanation: str = Field(
        description="Short explanation of what was changed and why (1-3 sentences)."
    )


class SubmitObservation(Observation):
    """Acknowledgement of submission."""


class _SubmitExecutor(ToolExecutor):
    def __init__(self, working_dir: str = ".") -> None:
        self._working_dir = working_dir

    def __call__(
        self,
        action: SubmitAction,
        conversation: "LocalConversation | None" = None,
    ) -> SubmitObservation:
        submission = {
            "submitted": True,
            "explanation": action.explanation,
        }
        path = os.path.join(self._working_dir, "SUBMISSION.json")
        with open(path, "w") as f:
            json.dump(submission, f, indent=2)

        # Signal the conversation loop to stop
        if conversation is not None:
            from openhands.sdk.conversation.state import ConversationExecutionStatus
            conversation._state.execution_status = ConversationExecutionStatus.FINISHED

        return SubmitObservation.from_text(
            "Submission recorded. Agent stopped."
        )


class SubmitTool(ToolDefinition[SubmitAction, SubmitObservation]):
    @classmethod
    def create(cls, conv_state=None, **_) -> Sequence["SubmitTool"]:
        working_dir = "."
        if conv_state is not None:
            working_dir = getattr(
                getattr(conv_state, "workspace", None), "working_dir", working_dir
            )
        return [
            cls(
                action_type=SubmitAction,
                observation_type=SubmitObservation,
                description=TOOL_DESCRIPTION,
                annotations=ToolAnnotations(
                    readOnlyHint=False,
                    destructiveHint=False,
                ),
                executor=_SubmitExecutor(working_dir=working_dir),
            )
        ]


register_tool(SubmitTool.name, SubmitTool)
