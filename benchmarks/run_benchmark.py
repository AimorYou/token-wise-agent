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

    # Docker mode (task code mounted at /testbed inside container)
    uv run python benchmarks/run_benchmark.py --docker task_001
    uv run python benchmarks/run_benchmark.py --docker --docker-build task_001
    uv run python benchmarks/run_benchmark.py --docker --docker-image myrepo/agent:v1 task_001
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent.config import AgentYamlConfig
from agent.utils import read_submission
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


DOCKER_IMAGE_DEFAULT = "token-wise-agent:latest"


def _build_agent_cmd(
    working_dir: str,
    issue_text: str,
    model: str | None,
    max_steps: int,
    agent_config_in_container: str | None,
    verbose: bool,
    run_id: str | None = None,
    task_id: str | None = None,
) -> list[str]:
    """Build the run.py argument list (shared between local and docker modes)."""
    cmd = ["--working-dir", working_dir, "--max-steps", str(max_steps), "--no-save-only-last-traj"]
    if model:
        cmd += ["--model", model]
    if agent_config_in_container:
        cmd += ["--agent-config", agent_config_in_container]
    if not verbose:
        cmd.append("--quiet")
    if run_id:
        cmd += ["--run-id", run_id]
    if task_id:
        cmd += ["--task-id", task_id]
    cmd.append(issue_text)
    return cmd


def _collect_result(workspace: Path, fallback_start: float) -> tuple[float, bool, str]:
    submitted, explanation = read_submission(workspace)
    metrics_path = workspace / "METRICS.json"
    try:
        latency = json.loads(metrics_path.read_text()).get("latency", 0.0)
    except (OSError, json.JSONDecodeError, KeyError):
        latency = round(time.time() - fallback_start, 1)
    return latency, submitted, explanation


def run_agent(
    workspace: Path,
    issue_text: str,
    model: str | None,
    max_steps: int,
    timeout: int,
    agent_config: str | None,
    verbose: bool = False,
    run_id: str | None = None,
    task_id: str | None = None,
) -> dict:
    """Запускаем агента через run.py (локально)."""
    cmd = [sys.executable, str(RUN_PY)]
    cmd += _build_agent_cmd(str(workspace), issue_text, model, max_steps, agent_config, verbose, run_id, task_id)

    start = time.time()
    try:
        if verbose:
            result = subprocess.run(cmd, text=True, timeout=timeout, stderr=subprocess.PIPE)
            result.stdout = ""
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        latency, submitted, explanation = _collect_result(workspace, start)
        return {
            "latency": latency,
            "submitted": submitted,
            "explanation": explanation,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        latency = round(time.time() - start, 1)
        console.print(f"  [red]Agent timed out after {timeout}s[/red]")
        return {
            "latency": latency,
            "submitted": False,
            "explanation": "",
            "stdout": "",
            "stderr": f"TIMEOUT after {timeout}s",
            "returncode": -1,
        }


def docker_image_exists(image: str) -> bool:
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
    )
    return result.returncode == 0


def docker_build(image: str) -> None:
    console.print(f"  [cyan]Building Docker image {image!r}...[/cyan]")
    result = subprocess.run(
        ["docker", "build", "-t", image, str(PROJECT_ROOT)],
        text=True,
    )
    if result.returncode != 0:
        console.print("[red]Docker build failed.[/red]")
        sys.exit(1)


def run_agent_docker(
    workspace: Path,
    issue_text: str,
    model: str | None,
    max_steps: int,
    timeout: int,
    agent_config: str | None,
    image: str,
    verbose: bool = False,
    run_id: str | None = None,
    task_id: str | None = None,
) -> dict:
    """Запускаем агента внутри Docker-контейнера.

    Task workspace монтируется в /testbed, агентский код живёт в /app образа.
    API-ключи пробрасываются через --env-file .env.
    """
    # Inside the container agent_config lives at /app/agent/agent_config.yaml by default.
    # If caller overrides it, we mount the file and pass the in-container path.
    extra_mounts: list[str] = []
    config_in_container: str | None = None
    if agent_config:
        host_cfg = Path(agent_config).resolve()
        config_in_container = f"/app/custom_agent_config.yaml"
        extra_mounts = ["-v", f"{host_cfg}:{config_in_container}:ro"]

    env_file = PROJECT_ROOT / ".env"
    agent_args = _build_agent_cmd("/testbed", issue_text, model, max_steps, config_in_container, verbose, run_id, task_id)

    cmd = ["docker", "run", "--rm"]
    cmd += ["-v", f"{workspace}:/testbed"]
    cmd += extra_mounts
    if env_file.exists():
        cmd += ["--env-file", str(env_file)]
    cmd += ["--timeout", str(timeout)] if False else []  # docker run has no --timeout; handled via subprocess
    cmd.append(image)
    cmd += agent_args

    start = time.time()
    try:
        if verbose:
            result = subprocess.run(cmd, text=True, timeout=timeout, stderr=subprocess.PIPE)
            result.stdout = ""
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        latency, submitted, explanation = _collect_result(workspace, start)
        return {
            "latency": latency,
            "submitted": submitted,
            "explanation": explanation,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        latency = round(time.time() - start, 1)
        console.print(f"  [red]Agent timed out after {timeout}s[/red]")
        return {
            "latency": latency,
            "submitted": False,
            "explanation": "",
            "stdout": "",
            "stderr": f"TIMEOUT after {timeout}s",
            "returncode": -1,
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
    timeout: int,
    agent_config: str | None,
    verbose: bool = False,
    docker: bool = False,
    docker_image: str = DOCKER_IMAGE_DEFAULT,
    run_id: str | None = None,
) -> dict:
    """Полный цикл для одной задачи."""
    task_id = task_dir.name
    with tempfile.TemporaryDirectory(prefix="bench_") as tmp_root:
        workspace = prepare_workspace(task_dir, Path(tmp_root))
        issue_text = (task_dir / "issue.md").read_text()

        mode = "[cyan]docker[/cyan]" if docker else "local"
        console.print(f"  Running agent ({mode})...")
        if docker:
            agent_result = run_agent_docker(
                workspace, issue_text, model, max_steps, timeout,
                agent_config, docker_image, verbose, run_id, task_id,
            )
        else:
            agent_result = run_agent(workspace, issue_text, model, max_steps, timeout, agent_config, verbose, run_id, task_id)

        console.print(f"  Agent finished in {agent_result['latency']}s, "
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
            "latency": agent_result["latency"],
            "test_output": test_result["test_output"],
            **metrics,
        }


def print_results_table(results: list[dict]) -> None:
    """Print per-task results as a rich table."""
    table = Table(title="Results", show_header=True, header_style="bold cyan", min_width=90)
    table.add_column("Task", style="bold", no_wrap=True)
    table.add_column("Status", justify="center", no_wrap=True)
    table.add_column("Tests", justify="center", no_wrap=True)
    table.add_column("LLM", justify="right", no_wrap=True)
    table.add_column("Tools", justify="right", no_wrap=True)
    table.add_column("Errs", justify="right", no_wrap=True)
    table.add_column("Cost", justify="right", no_wrap=True)
    table.add_column("Time", justify="right", no_wrap=True)

    for r in results:
        status = "[green]PASS[/green]" if r["tests_passed"] else "[red]FAIL[/red]"
        if not r["submitted"]:
            status = "[yellow]NO SUB[/yellow]"
        tp = r.get("tests_passed_count", 0)
        tt = r.get("tests_total", 0)

        task_name = r["task"].removeprefix("task_")
        table.add_row(
            task_name,
            status,
            f"{tp}/{tt}",
            str(r.get("llm_calls", "?")),
            str(r.get("total_tool_calls", "?")),
            str(r.get("tool_errors", "?")),
            f"${r.get('cost_usd', 0):.2f}",
            f"{r['latency']:.0f}s",
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
    total_latency = sum(r.get("latency", 0) for r in results)
    total_llm_calls = sum(r.get("llm_calls", 0) for r in results)
    total_tool_calls = sum(r.get("total_tool_calls", 0) for r in results)
    total_tool_errors = sum(r.get("tool_errors", 0) for r in results)
    total_input = sum(r.get("input_tokens", 0) for r in results)
    total_output = sum(r.get("output_tokens", 0) for r in results)
    total_cost = sum(r.get("cost_usd", 0) for r in results)

    tests_pct = round(100 * total_tp / total_tt) if total_tt > 0 else 0
    submit_pct = round(100 * tasks_submitted / n) if n > 0 else 0
    pass_pct = round(100 * tasks_passed / n) if n > 0 else 0

    table = Table(title="Summary", show_header=True, header_style="bold cyan", show_edge=True)
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    table.add_row("pass@1", f"{tasks_passed}/{n} ({pass_pct}%)")
    table.add_row("Submitted", f"{tasks_submitted}/{n} ({submit_pct}%)")
    table.add_row("Tests passed", f"{total_tp}/{total_tt} ({tests_pct}%)")
    table.add_row("", "")
    table.add_row("Input tokens", f"{total_input:,}")
    table.add_row("Output tokens", f"{total_output:,}")
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
    # Docker flags
    parser.add_argument("--docker", action="store_true", help="Run agent inside Docker container (task mounted at /testbed)")
    parser.add_argument("--docker-image", default=DOCKER_IMAGE_DEFAULT, help=f"Docker image to use (default: {DOCKER_IMAGE_DEFAULT})")
    parser.add_argument("--docker-build", action="store_true", help="Force rebuild of Docker image before running")
    args = parser.parse_args()

    task_dirs = sorted(d for d in TASKS_DIR.iterdir() if d.is_dir())
    if args.filter:
        task_dirs = [d for d in task_dirs if any(f in d.name for f in args.filter)]

    if not task_dirs:
        console.print("[red]No tasks found.[/red]")
        sys.exit(1)

    yaml_cfg = AgentYamlConfig.load(args.agent_config)
    timeout = yaml_cfg.timeout

    if args.docker:
        if args.docker_build or not docker_image_exists(args.docker_image):
            docker_build(args.docker_image)

    run_id = f"run_{datetime.now():%Y-%m-%d_%H-%M-%S}"
    console.print(f"Running {len(task_dirs)} task(s)... [dim]run_id={run_id}[/dim]\n")

    results = []
    for task_dir in task_dirs:
        console.rule(f"[bold]{task_dir.name}[/bold]")
        r = run_single_task(
            task_dir, args.model, args.max_steps, timeout, args.agent_config,
            verbose=not args.quiet,
            docker=args.docker,
            docker_image=args.docker_image,
            run_id=run_id,
        )
        results.append(r)

    print_results_table(results)
    print_summary_table(results)

    if args.save:
        Path(args.save).write_text(json.dumps(results, indent=2, ensure_ascii=False))
        console.print(f"\nResults saved to {args.save}")


if __name__ == "__main__":
    main()
