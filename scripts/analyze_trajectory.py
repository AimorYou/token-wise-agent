"""
Analyze a TRAJECTORY.traj.json file produced by run.py.

Usage:
    uv run python scripts/analyze_trajectory.py path/to/TRAJECTORY.traj.json
    uv run python scripts/analyze_trajectory.py path/to/TRAJECTORY.traj.json --raw
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from rich.console import Console
from rich.table import Table

console = Console()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def analyze(traj: dict) -> None:
    info = traj.get("info", {})
    messages = traj.get("messages", [])

    model_stats = info.get("model_stats", {})
    cfg = info.get("config", {})
    agent_cfg = cfg.get("agent", {})
    model_cfg = cfg.get("model", {})
    env_cfg = cfg.get("environment", {})

    # --- Run info ---
    run_info = Table(title="Run Info", show_header=False)
    run_info.add_column("Key", style="dim")
    run_info.add_column("Value")
    run_info.add_row("model",        model_cfg.get("model_name", "—"))
    run_info.add_row("exit_status",  info.get("exit_status", "—"))
    run_info.add_row("api_calls",    str(model_stats.get("api_calls", "—")))
    run_info.add_row("total cost",   f"${model_stats.get('instance_cost', 0):.4f}")
    run_info.add_row("step_limit",   str(agent_cfg.get("step_limit", "—")))
    run_info.add_row("cost_limit",   str(agent_cfg.get("cost_limit", "—")))
    run_info.add_row("cwd",          env_cfg.get("cwd", "—"))
    run_info.add_row("submitted",    "yes" if info.get("submission") else "no")
    console.print(run_info)
    console.print()

    # --- Token summary (from assistant messages) ---
    assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
    total_in = total_out = total_cache_create = total_cache_read = 0
    for msg in assistant_msgs:
        usage = (msg.get("extra") or {}).get("response", {}).get("usage", {})
        total_in           += usage.get("prompt_tokens", 0)
        total_out          += usage.get("completion_tokens", 0)
        total_cache_create += usage.get("cache_creation_input_tokens", 0)
        total_cache_read   += usage.get("cache_read_input_tokens", 0)

    tok = Table(title="Tokens", show_header=False)
    tok.add_column("Key", style="dim")
    tok.add_column("Value", justify="right")
    tok.add_row("Input tokens",       f"{total_in:,}")
    tok.add_row("Output tokens",      f"{total_out:,}")
    tok.add_row("Cache write tokens", f"{total_cache_create:,}")
    tok.add_row("Cache read tokens",  f"{total_cache_read:,}")
    console.print(tok)
    console.print()

    # --- Tool usage ---
    tool_calls: dict[str, int] = defaultdict(int)
    tool_chars: dict[str, int] = defaultdict(int)

    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    # Build map tool_call_id -> content length
    tc_chars: dict[str, int] = {m["tool_call_id"]: len(m.get("content") or "") for m in tool_msgs}

    for msg in assistant_msgs:
        for tc in msg.get("tool_calls") or []:
            name = tc.get("function", {}).get("name", "unknown")
            tool_calls[name] += 1
            tool_chars[name] += tc_chars.get(tc.get("id", ""), 0)

    total_chars = sum(tool_chars.values()) or 1
    vol = Table(title="Tool usage", show_header=True, header_style="bold cyan")
    vol.add_column("Tool", style="dim")
    vol.add_column("Calls", justify="right")
    vol.add_column("Chars returned", justify="right")
    vol.add_column("Share", justify="right")

    for tool, chars in sorted(tool_chars.items(), key=lambda x: -x[1]):
        pct = round(100 * chars / total_chars)
        vol.add_row(tool, str(tool_calls[tool]), f"{chars:,}", f"{pct}%")
    console.print(vol)
    console.print()

    # --- Per-step timeline ---
    timeline = Table(title="Step timeline", show_header=True, header_style="bold cyan")
    timeline.add_column("Step", justify="right")
    timeline.add_column("Tools")
    timeline.add_column("In tok", justify="right")
    timeline.add_column("Out tok", justify="right")
    timeline.add_column("Cost", justify="right")

    # Compute cost per step from usage (rough: proportional to output tokens, or use stored model_stats)
    # We don't store per-step cost in the new format — show token counts only.
    for i, msg in enumerate(assistant_msgs, 1):
        tools_str = ", ".join(
            tc.get("function", {}).get("name", "?")
            for tc in (msg.get("tool_calls") or [])
        ) or "—"
        usage = (msg.get("extra") or {}).get("response", {}).get("usage", {})
        timeline.add_row(
            str(i),
            tools_str,
            f"{usage.get('prompt_tokens', 0):,}",
            f"{usage.get('completion_tokens', 0):,}",
            "—",
        )
    console.print(timeline)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze agent TRAJECTORY.traj.json")
    parser.add_argument("path", help="Path to TRAJECTORY.traj.json")
    parser.add_argument("--raw", action="store_true", help="Print raw JSON")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        console.print(f"[red]File not found: {path}[/red]")
        sys.exit(1)

    traj = load(path)

    if args.raw:
        console.print_json(json.dumps(traj))
        return

    analyze(traj)


if __name__ == "__main__":
    main()
