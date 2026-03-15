"""
SmartEditorTool — безопасное и точное редактирование файлов агентом.

Поддерживаемые команды:
  patch   — применяет изменения в формате unified-style patch (основной способ)
  replace — точечная замена фрагмента (old → new), old должен встречаться ровно 1 раз
  insert  — вставка текста после указанной строки
  create  — создание нового файла
  delete  — удаление файла
  undo    — откат последнего изменения

Все изменения атомарны, работают только внутри рабочей директории,
и сохраняют историю для отката.
"""

import os
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from openhands.sdk.tool import Action, Observation, register_tool
from openhands.sdk.tool.tool import ToolAnnotations, ToolDefinition, ToolExecutor

if TYPE_CHECKING:
    from openhands.sdk.conversation import LocalConversation


# ---------------------------------------------------------------------------
# Edit history (per-executor instance, survives across tool calls)
# ---------------------------------------------------------------------------

class _EditRecord:
    """One undo-able change."""

    __slots__ = ("path", "old_content", "existed")

    def __init__(self, path: str, old_content: str | None, existed: bool) -> None:
        self.path = path
        self.old_content = old_content  # None means file didn't exist
        self.existed = existed


class _EditHistory:
    """Stack of edit records for undo support."""

    def __init__(self) -> None:
        self._stack: list[_EditRecord] = []

    def save(self, path: str) -> None:
        """Snapshot current state of *path* before modification."""
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            with open(abs_path, encoding="utf-8", errors="replace") as f:
                self._stack.append(_EditRecord(abs_path, f.read(), True))
        else:
            self._stack.append(_EditRecord(abs_path, None, False))

    def pop(self, path: str | None = None) -> _EditRecord | None:
        """Pop the latest record (optionally filtered by *path*)."""
        if path is not None:
            abs_path = os.path.abspath(path)
            for i in range(len(self._stack) - 1, -1, -1):
                if self._stack[i].path == abs_path:
                    return self._stack.pop(i)
            return None
        return self._stack.pop() if self._stack else None


# ---------------------------------------------------------------------------
# Patch parser  (*** Begin Patch … *** End Patch)
# ---------------------------------------------------------------------------

def _apply_patch(patch_text: str, working_dir: str) -> list[str]:
    """Parse and apply a structured patch. Returns list of affected file paths."""
    lines = patch_text.splitlines()
    affected: list[str] = []

    i = 0
    # Skip to *** Begin Patch (or treat whole text as patch body)
    while i < len(lines) and not lines[i].strip().startswith("*** Begin Patch"):
        i += 1
    if i < len(lines):
        i += 1  # skip the Begin Patch line

    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("*** End Patch"):
            break

        if line.startswith("*** Update File:"):
            rel_path = line.split(":", 1)[1].strip()
            abs_path = os.path.join(working_dir, rel_path)
            hunks, i = _parse_hunks(lines, i + 1)
            _apply_hunks_to_file(abs_path, hunks)
            affected.append(rel_path)

        elif line.startswith("*** Add File:"):
            rel_path = line.split(":", 1)[1].strip()
            abs_path = os.path.join(working_dir, rel_path)
            content_lines, i = _parse_add_content(lines, i + 1)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write("\n".join(content_lines))
                if content_lines:
                    f.write("\n")
            affected.append(rel_path)

        elif line.startswith("*** Delete File:"):
            rel_path = line.split(":", 1)[1].strip()
            abs_path = os.path.join(working_dir, rel_path)
            if os.path.exists(abs_path):
                os.remove(abs_path)
            affected.append(rel_path)

        else:
            i += 1
            continue

    return affected


def _parse_hunks(lines: list[str], start: int) -> tuple[list[dict], int]:
    """Parse consecutive @@ hunks until next *** directive or end."""
    hunks: list[dict] = []
    i = start

    while i < len(lines):
        stripped = lines[i].strip()

        if stripped.startswith("*** "):
            break

        if stripped.startswith("@@"):
            hunk: dict = {"context_before": [], "removals": [], "additions": [], "context_after": []}
            i += 1
            phase = "body"
            while i < len(lines):
                l = lines[i]
                stripped_l = l.strip()
                if stripped_l.startswith("@@") or stripped_l.startswith("*** "):
                    break
                if l.startswith("-"):
                    hunk["removals"].append(l[1:])  # strip leading -
                elif l.startswith("+"):
                    hunk["additions"].append(l[1:])  # strip leading +
                elif l.startswith(" "):
                    # Context line — goes to context_before if no removals/additions yet
                    if not hunk["removals"] and not hunk["additions"]:
                        hunk["context_before"].append(l[1:])
                    else:
                        hunk["context_after"].append(l[1:])
                i += 1
            hunks.append(hunk)
        else:
            i += 1

    return hunks, i


def _parse_add_content(lines: list[str], start: int) -> tuple[list[str], int]:
    """Parse content lines for *** Add File (all lines until next ***)."""
    content: list[str] = []
    i = start
    while i < len(lines):
        if lines[i].strip().startswith("*** "):
            break
        line = lines[i]
        # Strip leading + if present (patch format)
        if line.startswith("+"):
            line = line[1:]
        content.append(line)
        i += 1
    return content, i


def _apply_hunks_to_file(abs_path: str, hunks: list[dict]) -> None:
    """Apply parsed hunks to a file."""
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"File not found: {abs_path}")

    with open(abs_path, encoding="utf-8", errors="replace") as f:
        file_lines = f.read().splitlines()

    for hunk in hunks:
        ctx = hunk["context_before"]
        removals = hunk["removals"]
        additions = hunk["additions"]
        ctx_after = hunk["context_after"]

        # Build the "old" block = context_before + removals + context_after
        old_block = ctx + removals + ctx_after
        if not old_block:
            # No context/removals — just append additions at end
            file_lines.extend(additions)
            continue

        # Find the old block in file
        match_pos = _find_block(file_lines, old_block)
        if match_pos is None:
            # Try fuzzy: just removals with context
            old_block_min = removals if removals else ctx
            match_pos = _find_block(file_lines, old_block_min)
            if match_pos is None:
                snippet = "\n".join(old_block[:3])
                raise ValueError(
                    f"Cannot find matching block in {abs_path}:\n{snippet}..."
                )
            # Adjust: replace only the matched portion
            new_block = additions
            file_lines[match_pos : match_pos + len(old_block_min)] = new_block
            continue

        # Replace: keep context_before, swap removals for additions, keep context_after
        start = match_pos + len(ctx)
        end = start + len(removals)
        file_lines[start:end] = additions

    with open(abs_path, "w", encoding="utf-8") as f:
        f.write("\n".join(file_lines))
        if file_lines:
            f.write("\n")


def _find_block(file_lines: list[str], block: list[str]) -> int | None:
    """Find the starting line index of *block* in *file_lines* (stripped comparison)."""
    if not block:
        return None
    block_stripped = [l.strip() for l in block]
    for i in range(len(file_lines) - len(block) + 1):
        if all(
            file_lines[i + j].strip() == block_stripped[j]
            for j in range(len(block))
        ):
            return i
    return None


# ---------------------------------------------------------------------------
# Action / Observation
# ---------------------------------------------------------------------------

TOOL_DESCRIPTION = """\
Edit files safely and precisely. Supports six commands:

**patch** (preferred) — Apply changes in structured patch format:
  ```
  *** Begin Patch
  *** Update File: src/module.py
  @@
   context line before
  -old line to remove
  +new line to add
   context line after
  *** End Patch
  ```
  Can update, add, or delete multiple files in one patch.

**replace** — Replace exact text. `old` must occur exactly once in the file.
**insert** — Insert text after a given line number.
**create** — Create a new file (fails if it already exists).
**delete** — Delete a file.
**undo** — Undo the last edit (optionally for a specific file).

Always prefer `patch` for code changes — it's compact and handles multi-file edits.
Use `replace` for small single-occurrence fixes.
"""


class SmartEditorAction(Action):
    """Edit a file using one of the supported commands."""

    command: Literal["patch", "replace", "insert", "create", "delete", "undo"] = Field(
        description="The editing command to execute."
    )
    path: str | None = Field(
        default=None,
        description="File path (relative to working dir). Required for replace/insert/create/delete. Optional for undo.",
    )
    # patch
    diff: str | None = Field(
        default=None,
        description="Patch content in *** Begin Patch format. Required for 'patch' command.",
    )
    # replace
    old: str | None = Field(
        default=None,
        description="Exact text to find (must occur exactly once). Required for 'replace'.",
    )
    new: str | None = Field(
        default=None,
        description="Replacement text. Required for 'replace'.",
    )
    # insert
    line: int | None = Field(
        default=None,
        description="Line number after which to insert text (1-indexed). Required for 'insert'.",
    )
    text: str | None = Field(
        default=None,
        description="Text to insert. Required for 'insert'.",
    )
    # create
    content: str | None = Field(
        default=None,
        description="File content. Required for 'create'.",
    )


class SmartEditorObservation(Observation):
    """Result of an edit operation."""


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class _SmartEditorExecutor(ToolExecutor):
    def __init__(self) -> None:
        self._history = _EditHistory()

    def _resolve(self, path: str | None, working_dir: str) -> str | None:
        """Resolve relative path to absolute, validate it's inside working_dir."""
        if path is None:
            return None
        if os.path.isabs(path):
            abs_path = path
        else:
            abs_path = os.path.join(working_dir, path)
        abs_path = os.path.abspath(abs_path)
        wd = os.path.abspath(working_dir)
        if not abs_path.startswith(wd + os.sep) and abs_path != wd:
            return None  # outside working dir
        return abs_path

    def _get_working_dir(self, conversation) -> str:
        if conversation is not None:
            wd = getattr(getattr(conversation, "workspace", None), "working_dir", None)
            if wd:
                return wd
        return os.path.abspath(".")

    def __call__(
        self,
        action: SmartEditorAction,
        conversation: "LocalConversation | None" = None,
    ) -> SmartEditorObservation:
        working_dir = self._get_working_dir(conversation)
        cmd = action.command

        try:
            if cmd == "patch":
                return self._do_patch(action, working_dir)
            elif cmd == "replace":
                return self._do_replace(action, working_dir)
            elif cmd == "insert":
                return self._do_insert(action, working_dir)
            elif cmd == "create":
                return self._do_create(action, working_dir)
            elif cmd == "delete":
                return self._do_delete(action, working_dir)
            elif cmd == "undo":
                return self._do_undo(action, working_dir)
            else:
                return SmartEditorObservation.from_text(
                    f"Unknown command: {cmd}", is_error=True
                )
        except Exception as e:
            return SmartEditorObservation.from_text(str(e), is_error=True)

    # --- patch ---
    def _do_patch(self, action: SmartEditorAction, working_dir: str) -> SmartEditorObservation:
        if not action.diff:
            return SmartEditorObservation.from_text(
                "patch command requires 'diff' parameter.", is_error=True
            )
        # Save history for all files mentioned in patch
        file_paths = re.findall(
            r"\*\*\*\s+(?:Update|Add|Delete)\s+File:\s*(.+)",
            action.diff,
        )
        for rel in file_paths:
            abs_path = os.path.join(working_dir, rel.strip())
            self._history.save(abs_path)

        affected = _apply_patch(action.diff, working_dir)
        return SmartEditorObservation.from_text(
            f"Patch applied successfully to {len(affected)} file(s): {', '.join(affected)}"
        )

    # --- replace ---
    def _do_replace(self, action: SmartEditorAction, working_dir: str) -> SmartEditorObservation:
        if not action.path or action.old is None or action.new is None:
            return SmartEditorObservation.from_text(
                "replace command requires 'path', 'old', and 'new' parameters.", is_error=True
            )
        abs_path = self._resolve(action.path, working_dir)
        if abs_path is None:
            return SmartEditorObservation.from_text(
                f"Path '{action.path}' is outside the working directory.", is_error=True
            )
        if not os.path.exists(abs_path):
            return SmartEditorObservation.from_text(
                f"File not found: {action.path}", is_error=True
            )

        with open(abs_path, encoding="utf-8", errors="replace") as f:
            content = f.read()

        count = content.count(action.old)
        if count == 0:
            return SmartEditorObservation.from_text(
                f"Text not found in {action.path}. No changes made.", is_error=True
            )
        if count > 1:
            return SmartEditorObservation.from_text(
                f"Ambiguous: text occurs {count} times in {action.path}. "
                f"Provide more context to make the match unique.", is_error=True
            )

        self._history.save(abs_path)
        new_content = content.replace(action.old, action.new, 1)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return SmartEditorObservation.from_text(
            f"Replaced text in {action.path} successfully."
        )

    # --- insert ---
    def _do_insert(self, action: SmartEditorAction, working_dir: str) -> SmartEditorObservation:
        if not action.path or action.line is None or action.text is None:
            return SmartEditorObservation.from_text(
                "insert command requires 'path', 'line', and 'text' parameters.", is_error=True
            )
        abs_path = self._resolve(action.path, working_dir)
        if abs_path is None:
            return SmartEditorObservation.from_text(
                f"Path '{action.path}' is outside the working directory.", is_error=True
            )
        if not os.path.exists(abs_path):
            return SmartEditorObservation.from_text(
                f"File not found: {action.path}", is_error=True
            )

        with open(abs_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        self._history.save(abs_path)
        insert_idx = min(action.line, len(lines))
        new_lines = action.text.splitlines(keepends=True)
        # Ensure last line has newline
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        lines[insert_idx:insert_idx] = new_lines

        with open(abs_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

        return SmartEditorObservation.from_text(
            f"Inserted {len(new_lines)} line(s) after line {action.line} in {action.path}."
        )

    # --- create ---
    def _do_create(self, action: SmartEditorAction, working_dir: str) -> SmartEditorObservation:
        if not action.path or action.content is None:
            return SmartEditorObservation.from_text(
                "create command requires 'path' and 'content' parameters.", is_error=True
            )
        abs_path = self._resolve(action.path, working_dir)
        if abs_path is None:
            return SmartEditorObservation.from_text(
                f"Path '{action.path}' is outside the working directory.", is_error=True
            )
        if os.path.exists(abs_path):
            return SmartEditorObservation.from_text(
                f"File already exists: {action.path}. Use 'replace' or 'patch' to modify it.",
                is_error=True,
            )

        self._history.save(abs_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(action.content)

        return SmartEditorObservation.from_text(f"Created {action.path}.")

    # --- delete ---
    def _do_delete(self, action: SmartEditorAction, working_dir: str) -> SmartEditorObservation:
        if not action.path:
            return SmartEditorObservation.from_text(
                "delete command requires 'path' parameter.", is_error=True
            )
        abs_path = self._resolve(action.path, working_dir)
        if abs_path is None:
            return SmartEditorObservation.from_text(
                f"Path '{action.path}' is outside the working directory.", is_error=True
            )
        if not os.path.exists(abs_path):
            return SmartEditorObservation.from_text(
                f"File not found: {action.path}", is_error=True
            )

        self._history.save(abs_path)
        os.remove(abs_path)
        return SmartEditorObservation.from_text(f"Deleted {action.path}.")

    # --- undo ---
    def _do_undo(self, action: SmartEditorAction, working_dir: str) -> SmartEditorObservation:
        abs_path = self._resolve(action.path, working_dir) if action.path else None
        record = self._history.pop(abs_path)
        if record is None:
            return SmartEditorObservation.from_text(
                "Nothing to undo." + (f" (for {action.path})" if action.path else ""),
                is_error=True,
            )

        if record.existed:
            with open(record.path, "w", encoding="utf-8") as f:
                f.write(record.old_content)
            return SmartEditorObservation.from_text(f"Reverted {record.path}.")
        else:
            if os.path.exists(record.path):
                os.remove(record.path)
            return SmartEditorObservation.from_text(
                f"Undone: removed {record.path} (file did not exist before)."
            )


# ---------------------------------------------------------------------------
# Tool definition & registration
# ---------------------------------------------------------------------------

class SmartEditorTool(ToolDefinition[SmartEditorAction, SmartEditorObservation]):
    @classmethod
    def create(cls, conv_state=None, **_) -> Sequence["SmartEditorTool"]:
        return [
            cls(
                action_type=SmartEditorAction,
                observation_type=SmartEditorObservation,
                description=TOOL_DESCRIPTION,
                annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True),
                executor=_SmartEditorExecutor(),
            )
        ]


register_tool(SmartEditorTool.name, SmartEditorTool)
