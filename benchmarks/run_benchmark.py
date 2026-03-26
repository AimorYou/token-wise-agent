"""
SWE-Bench-style benchmark runner.

Запускает агента на задачах: подсовывает issue + код + существующие тесты
(без gold-тестов), ждёт пока агент вызовет submit, затем прогоняет
gold-тесты для оценки.

Структура задачи:
    task_XXX/
    ├── issue.md         — описание бага
    ├── src/             — код с багом
    ├── tests/           — существующие тесты (видны агенту, проходят на багнутом коде)
    └── gold_tests/      — gold-тесты (скрыты от агента, падают на багнутом коде)

Usage:
    uv run python benchmarks/run_benchmark.py                          # все задачи
    uv run python benchmarks/run_benchmark.py task_003                 # одна задача
    uv run python benchmarks/run_benchmark.py --model anthropic/claude-opus-4-6 task_001
    uv run python benchmarks/run_benchmark.py --quiet task_001
    uv run python benchmarks/run_benchmark.py --agent-config custom.yaml task_001
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = Path(__file__).resolve().parent / "tasks"
RUN_PY = PROJECT_ROOT / "run.py"

console = Console()


def prepare_workspace(task_dir: Path, tmp_root: Path) -> Path:
    """Копируем задачу во временную директорию БЕЗ gold_tests/."""
    workspace = tmp_root / task_dir.name
    shutil.copytree(
        task_dir, workspace,
        ignore=shutil.ignore_patterns("gold_tests", "__pycache__"),
    )
    return workspace


def run_agent(
    workspace: Path,
    issue_text: str,
    model: str | None,
    max_steps: int,
    agent_config: str | None,
    verbose: bool = False,
) -> dict:
    """Запускаем агента через run.py."""
    cmd = [sys.executable, str(RUN_PY)]
    cmd += ["--working-dir", str(workspace)]
    cmd += ["--max-steps", str(max_steps)]
    if model:
        cmd += ["--model", model]
    if agent_config:
        cmd += ["--agent-config", agent_config]
    if not verbose:
        cmd.append("--quiet")
    cmd.append(issue_text)

    start = time.time()
    if verbose:
        result = subprocess.run(cmd, text=True, timeout=300, stderr=subprocess.PIPE)
        result.stdout = ""
    else:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    elapsed = time.time() - start

    submission_path = workspace / "SUBMISSION.json"
    submitted = submission_path.exists()
    explanation = ""
    if submitted:
        data = json.loads(submission_path.read_text())
        explanation = data.get("explanation", "")

    return {
        "elapsed_seconds": round(elapsed, 1),
        "submitted": submitted,
        "explanation": explanation,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def run_gold_tests(task_dir: Path, workspace: Path) -> dict:
    """Copy gold_tests into workspace and run pytest, returning pass/fail counts."""
    gold_src = task_dir / "gold_tests"
    gold_dst = workspace / "gold_tests"
    if gold_dst.exists():
        shutil.rmtree(gold_dst)
    shutil.copytree(gold_src, gold_dst)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "gold_tests/"],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = result.stdout + result.stderr

    tests_total = 0
    tests_passed_count = 0
    m = re.search(r"(\d+) passed", output)
    if m:
        tests_passed_count = int(m.group(1))
        tests_total += tests_passed_count
    m = re.search(r"(\d+) failed", output)
    if m:
        tests_total += int(m.group(1))
    m = re.search(r"(\d+) error", output)
    if m:
        tests_total += int(m.group(1))

    return {
        "all_passed": result.returncode == 0,
        "tests_passed_count": tests_passed_count,
        "tests_total": tests_total,
        "test_output": output,
    }


def read_metrics(workspace: Path) -> dict:
    """Read METRICS.json written by run.py after agent finishes."""
    metrics_path = workspace / "METRICS.json"
    if not metrics_path.exists():
        return {}
    try:
        data = json.loads(metrics_path.read_text())
        return {
            "llm_calls": data.get("llm_calls", 0),
            "input_tokens": data.get("total_input_tokens", 0),
            "output_tokens": data.get("total_output_tokens", 0),
            "cache_write_tokens": data.get("total_cache_write_tokens", 0),
            "cache_read_tokens": data.get("total_cache_read_tokens", 0),
            "cost_usd": data.get("total_cost_usd", 0),
            "total_tool_calls": data.get("total_tool_calls", 0),
            "tool_errors": data.get("tool_errors", 0),
        }
    except (json.JSONDecodeError, KeyError):
        return {}


def run_single_task(
    task_dir: Path,
    model: str | None,
    max_steps: int,
    agent_config: str | None,
    verbose: bool = False,
) -> dict:
    """Полный цикл для одной задачи."""
    with tempfile.TemporaryDirectory(prefix="bench_") as tmp_root:
        workspace = prepare_workspace(task_dir, Path(tmp_root))
        issue_text = (task_dir / "issue.md").read_text()

        console.print(f"  Running agent...")
        agent_result = run_agent(workspace, issue_text, model, max_steps, agent_config, verbose)

        console.print(f"  Agent finished in {agent_result['elapsed_seconds']}s, "
                       f"submitted={agent_result['submitted']}")

        if agent_result["explanation"]:
            console.print(f"  Explanation: {agent_result['explanation']}")

        console.print(f"  Running gold tests...")
        test_result = run_gold_tests(task_dir, workspace)

        passed = test_result["all_passed"]
        tp = test_result["tests_passed_count"]
        tt = test_result["tests_total"]
        pct = round(100 * tp / tt) if tt > 0 else 0
        status = "[bold green]PASS[/bold green]" if passed else "[bold red]FAIL[/bold red]"
        console.print(f"  Gold tests: {status} ({tp}/{tt}, {pct}%)")

        metrics = read_metrics(workspace)

        return {
            "task": task_dir.name,
            "submitted": agent_result["submitted"],
            "explanation": agent_result["explanation"],
            "tests_passed": passed,
            "tests_passed_count": tp,
            "tests_total": tt,
            "elapsed_seconds": agent_result["elapsed_seconds"],
            "test_output": test_result["test_output"],
            **metrics,
        }


def print_results_table(results: list[dict]) -> None:
    """Print per-task results as a rich table."""
    table = Table(title="Results", show_header=True, header_style="bold cyan")
    table.add_column("Task", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Tests", justify="center")
    table.add_column("LLM calls", justify="right")
    table.add_column("Tool calls", justify="right")
    table.add_column("Errors", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("Time", justify="right")

    for r in results:
        status = "[green]PASS[/green]" if r["tests_passed"] else "[red]FAIL[/red]"
        if not r["submitted"]:
            status = "[yellow]NO SUBMIT[/yellow]"
        tp = r.get("tests_passed_count", 0)
        tt = r.get("tests_total", 0)
        tests_str = f"{tp}/{tt}"

        table.add_row(
            r["task"],
            status,
            tests_str,
            str(r.get("llm_calls", "?")),
            str(r.get("total_tool_calls", "?")),
            str(r.get("tool_errors", "?")),
            f"${r.get('cost_usd', 0):.4f}",
            f"{r['elapsed_seconds']}s",
        )

    console.print()
    console.print(table)


def print_summary_table(results: list[dict]) -> None:
    """Print aggregate summary as a rich table."""
    n = len(results)
    tasks_passed = sum(1 for r in results if r["tests_passed"] and r["submitted"])
    tasks_submitted = sum(1 for r in results if r["submitted"])
    total_tp = sum(r.get("tests_passed_count", 0) for r in results)
    total_tt = sum(r.get("tests_total", 0) for r in results)
    total_latency = sum(r.get("elapsed_seconds", 0) for r in results)
    total_llm_calls = sum(r.get("llm_calls", 0) for r in results)
    total_tool_calls = sum(r.get("total_tool_calls", 0) for r in results)
    total_tool_errors = sum(r.get("tool_errors", 0) for r in results)
    total_input = sum(r.get("input_tokens", 0) for r in results)
    total_output = sum(r.get("output_tokens", 0) for r in results)
    total_cache_write = sum(r.get("cache_write_tokens", 0) for r in results)
    total_cache_read = sum(r.get("cache_read_tokens", 0) for r in results)
    total_cost = sum(r.get("cost_usd", 0) for r in results)

    tests_pct = round(100 * total_tp / total_tt) if total_tt > 0 else 0
    pass_pct = round(100 * tasks_passed / n) if n > 0 else 0

    table = Table(title="Summary", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    table.add_row("pass@1", f"{tasks_passed}/{n} ({pass_pct}%)")
    table.add_row("Submitted", f"{tasks_submitted}/{n}")
    table.add_row("Tests passed", f"{total_tp}/{total_tt} ({tests_pct}%)")
    table.add_row("", "")
    table.add_row("Input tokens", f"{total_input:,}")
    table.add_row("Output tokens", f"{total_output:,}")
    table.add_row("Cache write tokens", f"{total_cache_write:,}")
    table.add_row("Cache read tokens", f"{total_cache_read:,}")
    table.add_row("Total cost", f"${total_cost:.4f}")
    table.add_row("", "")
    table.add_row("Avg latency", f"{total_latency / n:.1f}s" if n else "—")
    table.add_row("LLM calls", str(total_llm_calls))
    table.add_row("Total tool calls", str(total_tool_calls))
    table.add_row("Tool errors", str(total_tool_errors))

    console.print()
    console.print(table)


def main():
    parser = argparse.ArgumentParser(description="SWE-Bench-style benchmark runner")
    parser.add_argument("filter", nargs="*", help="Task name filters (e.g. task_001 task_003)")
    parser.add_argument("--model", help="Model override (e.g. anthropic/claude-opus-4-6)")
    parser.add_argument("--max-steps", type=int, default=30, help="Max agent steps (default: 30)")
    parser.add_argument("--agent-config", help="Path to agent config YAML override")
    parser.add_argument("--quiet", action="store_true", help="Suppress agent thoughts and tool calls")
    parser.add_argument("--save", help="Save results to JSON file")
    args = parser.parse_args()

    task_dirs = sorted(d for d in TASKS_DIR.iterdir() if d.is_dir())
    if args.filter:
        task_dirs = [d for d in task_dirs if any(f in d.name for f in args.filter)]

    if not task_dirs:
        console.print("[red]No tasks found.[/red]")
        sys.exit(1)

    console.print(f"Running {len(task_dirs)} task(s)...\n")

    results = []
    for task_dir in task_dirs:
        console.rule(f"[bold]{task_dir.name}[/bold]")
        r = run_single_task(task_dir, args.model, args.max_steps, args.agent_config, not args.quiet)
        results.append(r)

    print_results_table(results)
    print_summary_table(results)

    if args.save:
        Path(args.save).write_text(json.dumps(results, indent=2, ensure_ascii=False))
        console.print(f"\nResults saved to {args.save}")


if __name__ == "__main__":
    main()
