"""
Trajectory writer — dumps agent run to a .traj.json file.

Output path: {user_config_dir("token-wise-agent")}/{run_id}/{task_id}.traj.json

Format (compatible with SWE-bench / mini-swe-agent):

  {
    "info": {
      "run_id": "run_2026-04-05_12-00-00",
      "task_id": "task-001-fix-foo",\
      "started_at": "2026-04-05T12:00:00Z",
      "finished_at": "2026-04-05T12:01:30Z",
      "model_stats": { "instance_cost": 0.0, "api_calls": 15, "latency": 90.0 },
      "config": { "agent": {...}, "model": {...}, "environment": {...} },
      "exit_status": "submitted | step_limit | cost_limit | timeout | <ExcType>",
      "submission": "<patch content or empty string>"
    },
    "messages": [ ... ]
  }
"""

import json
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TYPE_CHECKING

from platformdirs import user_config_dir

from agent.agent_tracker import AgentTracker

if TYPE_CHECKING:
    from agent.config import AgentConfig

_APP_NAME = "token-wise-agent"


def get_trajectory_path(run_id: str, task_id: str) -> Path:
    """Return absolute path for a full (per-task) trajectory file."""
    return Path(user_config_dir(_APP_NAME)) / run_id / f"{task_id}.traj.json"


def get_last_trajectory_path() -> Path:
    """Return path for the 'last run' trajectory (overwritten each run)."""
    return Path(user_config_dir(_APP_NAME)) / "last_twa_run.traj.json"


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def write_trajectory(
    path: Path,
    run_id: str,
    task_id: str,
    started_at: str,
    tracker: AgentTracker,
    events: Any,
    config: "AgentConfig",
    rendered_task: str,
    system_prompt: str,
    exit_status: str,
    submission_content: str = "",
) -> None:
    """Write full run trajectory to a .traj.json file."""
    from openhands.sdk.event import ActionEvent, ObservationEvent

    yaml_cfg = config.yaml_config
    finished_at = _now_iso()

    # ------------------------------------------------------------------ #
    # Build step_order and step_actions from events                        #
    # ------------------------------------------------------------------ #
    step_order: list[str] = []
    step_actions: dict[str, list] = defaultdict(list)

    for event in events:
        if isinstance(event, ActionEvent) and event.tool_name:
            resp_id = str(event.llm_response_id)
            if resp_id not in step_actions:
                step_order.append(resp_id)
            step_actions[resp_id].append(event)

    # ------------------------------------------------------------------ #
    # Pair ObservationEvents with ActionEvents sequentially (FIFO)         #
    # ------------------------------------------------------------------ #
    flat_pending: deque[tuple[str, str]] = deque()
    for resp_id in step_order:
        for action in step_actions[resp_id]:
            flat_pending.append((resp_id, _tool_call_id(action)))

    tool_results: dict[str, str] = {}

    for event in events:
        if isinstance(event, ObservationEvent):
            tc_id = getattr(event, "tool_call_id", None)
            if tc_id:
                flat_pending.popleft()
            elif flat_pending:
                _, tc_id = flat_pending.popleft()
            if tc_id:
                tool_results[tc_id] = _obs_text(event)

    # ------------------------------------------------------------------ #
    # Build messages array                                                 #
    # ------------------------------------------------------------------ #
    messages: list[dict] = []
    messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": rendered_task})

    for step_idx, resp_id in enumerate(step_order, 1):
        actions = step_actions[resp_id]
        tool_calls_json = []

        # Collect thought text from first action in this step
        thought_text: str | None = None
        first_action = actions[0] if actions else None
        if first_action is not None:
            thought = getattr(first_action, "thought", None)
            if thought:
                parts = [getattr(c, "text", "") for c in thought if hasattr(c, "text")]
                thought_text = "".join(parts) or None

        for action in actions:
            tc_id = _tool_call_id(action)
            args = _tool_args(action)
            tool_calls_json.append({
                "id": tc_id,
                "type": "function",
                "function": {"name": action.tool_name, "arguments": args},
            })

        if step_idx <= len(tracker.steps):
            s = tracker.steps[step_idx - 1]
            usage = {
                "output_tokens": s.output_tokens,
                "input_tokens": s.input_tokens,
                "total_tokens": s.input_tokens + s.output_tokens,
                "cost": round(s.cost(tracker.model), 6),
            }
        else:
            usage = {}

        messages.append({
            "role": "assistant",
            "content": thought_text,
            "tool_calls": tool_calls_json,
            "usage": usage,
        })

        for action in actions:
            tc_id = _tool_call_id(action)
            messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "tool_name": action.tool_name,
                "content": tool_results.get(tc_id, ""),
            })

    # ------------------------------------------------------------------ #
    # info section                                                         #
    # ------------------------------------------------------------------ #
    info = {
        "run_id": run_id,
        "task_id": task_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "model_stats": {
            "instance_cost": round(tracker.total_cost, 6),
            "api_calls": tracker.llm_calls,
            "latency": tracker.latency,
            "total_input_tokens": tracker.total_input,
            "total_output_tokens": tracker.total_output,
            "total_tool_calls": tracker.total_tool_calls,
            "tool_errors": tracker.tool_errors,
        },
        "config": {
            "agent": {
                "system_template": system_prompt,
                "instance_template": yaml_cfg.instance_template,
                "step_limit": config.effective_max_steps,
                "cost_limit": yaml_cfg.cost_limit,
                "output_path": str(path),
            },
            "model": {
                "model_name": config.model,
                "model_kwargs": yaml_cfg.llm_params,
                "base_url": config.base_url,
            },
            "environment": {
                "cwd": config.working_dir,
                "timeout": yaml_cfg.timeout,
            },
        },
        "exit_status": exit_status,
        "submission": submission_content,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"info": info, "messages": messages}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _tool_call_id(action: Any) -> str:
    tc = getattr(action, "tool_call", None)
    if tc:
        tc_id = getattr(tc, "id", None)
        if tc_id:
            return str(tc_id)
    return f"call_{action.llm_response_id}_{action.tool_name}"


def _tool_args(action: Any) -> str:
    tc = getattr(action, "tool_call", None)
    if tc is None:
        return "{}"
    args = getattr(tc, "arguments", None)
    if args is None:
        return "{}"
    if isinstance(args, str):
        return args
    return json.dumps(args, ensure_ascii=False)


def _obs_text(event: Any) -> str:
    obs = getattr(event, "observation", None)
    if obs is None:
        return ""
    content = getattr(obs, "content", None)
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return "".join(getattr(c, "text", "") for c in content)
