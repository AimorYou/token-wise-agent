"""
Analyze trajectory files produced by run.py.

Usage:
    uv run python scripts/analyze_trajectory.py                     # last run
    uv run python scripts/analyze_trajectory.py path/to/run_dir/    # all trajs in dir
    uv run python scripts/analyze_trajectory.py path/to/file.traj.json
"""

import json
import sys
from pathlib import Path

from platformdirs import user_config_dir
from rich.console import Console
from rich.table import Table

_APP_NAME = "token-wise-agent"

console = Console()

_TOOL_CATEGORY: dict[str, str] = {
    "glob":         "read",
    "grep":         "read",
    "smart_reader": "read",
    "smart_editor": "write",
    "bash":         "execute",
    "bash_session": "execute",
}
_CATEGORIES = ("read", "write", "execute", "test")
_TEST_PATTERNS = ("pytest", "python -m pytest", "-m pytest", "unittest")


def _cat(tool_name: str, args_json: str = "") -> str:
    base = _TOOL_CATEGORY.get(tool_name, "execute")
    if base == "execute" and args_json:
        try:
            args = json.loads(args_json)
            cmd = args.get("command", "") if isinstance(args, dict) else ""
        except (json.JSONDecodeError, TypeError):
            cmd = args_json
        if any(p in cmd for p in _TEST_PATTERNS):
            return "test"
    return base


def _strip_task_prefix(task_id: str) -> str:
    return task_id.removeprefix("task_")


def _collect_metrics(traj: dict) -> dict:
    info = traj.get("info", {})
    messages = traj.get("messages", [])
    model_stats = info.get("model_stats", {})

    reasoning_chars = 0
    action_chars = 0
    obs_chars = 0

    action_by_cat: dict[str, int] = {c: 0 for c in _CATEGORIES}
    obs_by_cat: dict[str, int] = {c: 0 for c in _CATEGORIES}

    # Build tool_call_id -> (tool_name, content_len) from tool messages
    tc_info: dict[str, tuple[str, int]] = {}
    for m in messages:
        if m.get("role") == "tool":
            tc_id = m.get("tool_call_id", "")
            tool_name = m.get("tool_name") or ""
            chars = len(m.get("content") or "")
            tc_info[tc_id] = (tool_name, chars)
            obs_chars += chars

    for m in messages:
        if m.get("role") != "assistant":
            continue

        reasoning_chars += len(m.get("content") or "")

        for tc in m.get("tool_calls") or []:
            fn = tc.get("function", {})
            tool_name = fn.get("name", "")
            args_json = fn.get("arguments") or ""

            # think → reasoning chars, not tool input
            if tool_name == "think":
                try:
                    reasoning_chars += len(json.loads(args_json).get("thought", ""))
                except (json.JSONDecodeError, TypeError, AttributeError):
                    pass
                continue

            # submit and think don't count as tool input/output
            if tool_name == "submit":
                continue

            args_len = len(args_json)
            action_chars += args_len
            cat = _cat(tool_name, args_json)
            action_by_cat[cat] += args_len

            tc_id = tc.get("id", "")
            if tc_id in tc_info:
                obs_tool_name, obs_len = tc_info[tc_id]
                effective_name = obs_tool_name or tool_name
                obs_cat = _cat(effective_name, args_json)
                obs_by_cat[obs_cat] += obs_len

    submission = info.get("submission") or ""
    try:
        submit_explanation = json.loads(submission).get("explanation", "") if submission else ""
    except (json.JSONDecodeError, AttributeError):
        submit_explanation = submission

    return {
        "task_id":      _strip_task_prefix(info.get("task_id", "—")),
        "exit_status":  info.get("exit_status", "—"),
        "api_calls":    model_stats.get("api_calls", 0),
        "cost":         model_stats.get("instance_cost", 0.0),
        "latency":      model_stats.get("latency", 0.0),
        "reasoning":    reasoning_chars,
        "action":       action_chars,
        "observation":  obs_chars,
        "submit":       len(submit_explanation),
        "action_read":  action_by_cat["read"],
        "action_write": action_by_cat["write"],
        "action_exec":  action_by_cat["execute"],
        "action_test":  action_by_cat["test"],
        "obs_read":     obs_by_cat["read"],
        "obs_write":    obs_by_cat["write"],
        "obs_exec":     obs_by_cat["execute"],
        "obs_test":     obs_by_cat["test"],
    }


def _avg(rows: list[dict], key: str) -> float:
    vals = [r[key] for r in rows]
    return sum(vals) / len(vals) if vals else 0.0


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


def print_summary(rows: list[dict]) -> None:
    t = Table(title="Trajectory Summary", show_header=True, header_style="bold cyan")
    t.add_column("Task",     style="bold", no_wrap=True)
    t.add_column("Exit",     justify="center", no_wrap=True)
    t.add_column("Calls",    justify="right")
    t.add_column("Cost",     justify="right")
    t.add_column("Time",     justify="right")
    t.add_column("Think",    justify="right")
    t.add_column("T.In",     justify="right")
    t.add_column("T.Out",    justify="right")
    t.add_column("Submit",   justify="right")

    for r in rows:
        color = "green" if r["exit_status"] == "submitted" else "red"
        t.add_row(
            r["task_id"],
            f"[{color}]{r['exit_status']}[/{color}]",
            str(r["api_calls"]),
            f"${r['cost']:.4f}",
            f"{r['latency']}s",
            _fmt(r["reasoning"]),
            _fmt(r["action"]),
            _fmt(r["observation"]),
            _fmt(r["submit"]),
        )

    if len(rows) > 1:
        t.add_section()
        t.add_row(
            "[dim]avg[/dim]", "—",
            f"{_avg(rows, 'api_calls'):.1f}",
            f"${_avg(rows, 'cost'):.4f}",
            f"{_avg(rows, 'latency'):.1f}s",
            _fmt(int(_avg(rows, "reasoning"))),
            _fmt(int(_avg(rows, "action"))),
            _fmt(int(_avg(rows, "observation"))),
            _fmt(int(_avg(rows, "submit"))),
        )

    console.print(t)


def print_breakdown(rows: list[dict]) -> None:
    # Print category labels manually as a pseudo-header row
    cats = ("Read", "Write", "Execute", "Test")

    t = Table(title="Tool Breakdown  (In = chars sent, Out = chars received)",
              show_header=True, header_style="bold cyan")
    t.add_column("Task", style="bold", no_wrap=True)
    for cat in cats:
        t.add_column(f"{cat} In",  justify="right", no_wrap=True)
        t.add_column(f"{cat} Out", justify="right", no_wrap=True)

    def _row_vals(r: dict) -> list[str]:
        return [
            v for c in ("read", "write", "exec", "test")
            for v in (_fmt(r[f"action_{c}"]), _fmt(r[f"obs_{c}"]))
        ]

    for r in rows:
        t.add_row(r["task_id"], *_row_vals(r))

    if len(rows) > 1:
        avg_r = (
            {f"action_{c}": int(_avg(rows, f"action_{c}")) for c in ("read", "write", "exec", "test")}
            | {f"obs_{c}": int(_avg(rows, f"obs_{c}")) for c in ("read", "write", "exec", "test")}
        )
        t.add_section()
        t.add_row("[dim]avg[/dim]", *_row_vals(avg_r))

    console.print(t)


def resolve_paths(arg: str | None) -> list[Path]:
    if arg is None:
        p = Path(user_config_dir(_APP_NAME)) / "last_twa_run.traj.json"
        if not p.exists():
            run_dir = Path(user_config_dir(_APP_NAME))
            dirs = sorted(
                (d for d in run_dir.iterdir() if d.is_dir()),
                key=lambda d: d.stat().st_mtime,
            )
            if dirs:
                return sorted(dirs[-1].glob("*.traj.json"))
            console.print("[red]No trajectory files found.[/red]")
            sys.exit(1)
        return [p]

    p = Path(arg)
    if not p.exists():
        # Try resolving as a run_id inside the config dir
        candidate = Path(user_config_dir(_APP_NAME)) / arg
        if candidate.exists():
            p = candidate
        else:
            console.print(f"[red]Not found: {p}[/red]")
            sys.exit(1)
    if p.is_dir():
        files = sorted(p.glob("*.traj.json"))
        if not files:
            console.print(f"[red]No .traj.json files in {p}[/red]")
            sys.exit(1)
        return files
    return [p]


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Analyze agent trajectory files")
    parser.add_argument("path", nargs="?", help="File or directory (default: last run)")
    args = parser.parse_args()

    paths = resolve_paths(args.path)
    rows = [_collect_metrics(json.loads(p.read_text(encoding="utf-8"))) for p in paths]

    source = paths[0].parent if len(paths) > 1 else paths[0]
    console.print(f"\n[bold]Analyzing:[/bold] {source}\n")

    print_summary(rows)
    console.print()
    print_breakdown(rows)


if __name__ == "__main__":
    main()
