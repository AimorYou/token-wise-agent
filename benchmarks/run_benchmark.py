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

Промпт формируется агентом — runner только передаёт текст issue.md.
Шаблоны промптов живут в agent/agent_config.yaml и agent/prompts/.

Usage:
    uv run python benchmarks/run_benchmark.py                          # все задачи
    uv run python benchmarks/run_benchmark.py task_003                 # одна задача
    uv run python benchmarks/run_benchmark.py --model anthropic/claude-opus-4-6 task_001
    uv run python benchmarks/run_benchmark.py --quiet task_001
    uv run python benchmarks/run_benchmark.py --agent-config custom.yaml task_001
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = Path(__file__).resolve().parent / "tasks"
RUN_PY = PROJECT_ROOT / "run.py"


def prepare_workspace(task_dir: Path, tmp_root: Path) -> Path:
    """Копируем задачу во временную директорию БЕЗ gold_tests/.

    tests/ (существующие тесты) копируются — агент их видит.
    gold_tests/ (оценочные тесты) НЕ копируются — агент их не видит.
    """
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
    """Запускаем агента через run.py — всё через CLI аргументы."""
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

    # Проверяем, создал ли агент SUBMISSION.json
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


def run_tests(task_dir: Path, workspace: Path) -> dict:
    """Копируем тесты в workspace и запускаем pytest."""
    tests_src = task_dir / "tests"
    tests_dst = workspace / "tests"
    if tests_dst.exists():
        shutil.rmtree(tests_dst)
    shutil.copytree(tests_src, tests_dst)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "tests/"],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return {
        "tests_passed": result.returncode == 0,
        "test_output": result.stdout + result.stderr,
        "returncode": result.returncode,
    }


def read_metrics(workspace: Path) -> dict:
    """Read METRICS.json written by run.py after agent finishes."""
    metrics_path = workspace / "METRICS.json"
    if not metrics_path.exists():
        return {}
    try:
        data = json.loads(metrics_path.read_text())
        return {
            "steps": data.get("steps", 0),
            "input_tokens": data.get("total_input_tokens", 0),
            "output_tokens": data.get("total_output_tokens", 0),
            "cost_usd": f"${data.get('total_cost_usd', 0):.4f}",
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

        print(f"  Running agent...")
        agent_result = run_agent(workspace, issue_text, model, max_steps, agent_config, verbose)

        print(f"  Agent finished in {agent_result['elapsed_seconds']}s, "
              f"submitted={agent_result['submitted']}")

        if agent_result["explanation"]:
            print(f"  Explanation: {agent_result['explanation']}")

        print(f"  Running tests...")
        test_result = run_tests(task_dir, workspace)

        passed = test_result["tests_passed"]
        print(f"  Tests: {'PASS' if passed else 'FAIL'}")

        tokens = read_metrics(workspace)

        return {
            "task": task_dir.name,
            "submitted": agent_result["submitted"],
            "explanation": agent_result["explanation"],
            "tests_passed": passed,
            "elapsed_seconds": agent_result["elapsed_seconds"],
            "test_output": test_result["test_output"],
            **tokens,
        }


def main():
    parser = argparse.ArgumentParser(description="SWE-Bench-style benchmark runner")
    parser.add_argument("filter", nargs="?", help="Task name filter (e.g. task_001)")
    parser.add_argument("--model", help="Model override (e.g. anthropic/claude-opus-4-6)")
    parser.add_argument("--max-steps", type=int, default=30, help="Max agent steps (default: 30)")
    parser.add_argument("--agent-config", help="Path to agent config YAML override")
    parser.add_argument("--quiet", action="store_true", help="Suppress agent thoughts and tool calls")
    parser.add_argument("--save", help="Save results to JSON file")
    args = parser.parse_args()

    task_dirs = sorted(d for d in TASKS_DIR.iterdir() if d.is_dir())
    if args.filter:
        task_dirs = [d for d in task_dirs if args.filter in d.name]

    if not task_dirs:
        print("No tasks found.")
        sys.exit(1)

    print(f"Running {len(task_dirs)} task(s)...\n")

    results = []
    for task_dir in task_dirs:
        print(f"{'='*60}")
        print(f"Task: {task_dir.name}")
        print(f"{'='*60}")
        r = run_single_task(task_dir, args.model, args.max_steps, args.agent_config, not args.quiet)
        results.append(r)
        print()

    # Summary
    print(f"{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for r in results:
        status = "PASS" if r["tests_passed"] else "FAIL"
        submit = "submitted" if r["submitted"] else "NO SUBMIT"
        steps = r.get("steps", "?")
        cost = r.get("cost_usd", "?")
        print(f"  [{status}] [{submit}] {r['task']}  "
              f"(steps={steps}, cost={cost}, time={r['elapsed_seconds']}s)")

    passed = sum(1 for r in results if r["tests_passed"])
    print(f"\n{passed}/{len(results)} tasks passed")

    if args.save:
        Path(args.save).write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"Results saved to {args.save}")


if __name__ == "__main__":
    main()
