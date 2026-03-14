"""
SWE-Bench-style benchmark runner.

Запускает агента на задачах: подсовывает issue + код (без тестов),
ждёт пока агент вызовет submit, затем прогоняет тесты.

Промпт формируется агентом — runner только передаёт текст issue.md.
Шаблоны промптов живут в agent/prompt_config.yaml и agent/prompts/.

Usage:
    uv run python benchmarks/run_benchmark.py                          # все задачи
    uv run python benchmarks/run_benchmark.py task_003                 # одна задача
    uv run python benchmarks/run_benchmark.py --model anthropic/claude-opus-4-6 task_001
    uv run python benchmarks/run_benchmark.py --prompt-config custom.yaml task_001
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
    """Копируем задачу во временную директорию БЕЗ tests/."""
    workspace = tmp_root / task_dir.name
    shutil.copytree(task_dir, workspace, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    return workspace


def run_agent(
    workspace: Path,
    issue_text: str,
    model: str | None,
    max_steps: int,
    prompt_config: str | None,
    verbose: bool = False,
) -> dict:
    """Запускаем агента через run.py — передаём только текст issue."""
    env = {
        **dict(__import__("os").environ),
        "AGENT_WORKING_DIR": str(workspace),
        "AGENT_MAX_STEPS": str(max_steps),
        "AGENT_VERBOSE": "true" if verbose else "false",
    }
    if model:
        env["AGENT_MODEL"] = model

    cmd = [sys.executable, str(RUN_PY)]
    if prompt_config:
        cmd += ["--prompt-config", prompt_config]
    if not verbose:
        cmd.append("--quiet")
    cmd.append(issue_text)

    start = time.time()
    # verbose: вывод агента идёт прямо в терминал; quiet: захватываем stdout
    if verbose:
        result = subprocess.run(cmd, text=True, env=env, timeout=300,
                                stderr=subprocess.PIPE)
        result.stdout = ""  # вывод ушёл в терминал, парсить нечего
    else:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=300)
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


def extract_token_summary(stdout: str) -> dict:
    """Парсим Token Usage Summary из вывода агента.""" # FIXME: Не работает
    summary = {}
    for line in stdout.splitlines():
        line = line.strip()
        if "│" in line:
            parts = [p.strip() for p in line.split("│")]
            if len(parts) >= 2:
                key, value = parts[0], parts[1]
                if key == "Steps":
                    summary["steps"] = int(value)
                elif key == "Input tokens":
                    summary["input_tokens"] = int(value.replace(",", ""))
                elif key == "Output tokens":
                    summary["output_tokens"] = int(value.replace(",", ""))
                elif key == "Estimated cost":
                    summary["cost_usd"] = value
    return summary


def run_single_task(
    task_dir: Path,
    model: str | None,
    max_steps: int,
    prompt_config: str | None,
    verbose: bool = False,
) -> dict:
    """Полный цикл для одной задачи."""
    with tempfile.TemporaryDirectory(prefix="bench_") as tmp_root:
        workspace = prepare_workspace(task_dir, Path(tmp_root))

        # Читаем issue.md — это сырой "task", агент сам оборачивает его в instance_template
        issue_text = (task_dir / "issue.md").read_text()

        print(f"  Running agent...")
        agent_result = run_agent(workspace, issue_text, model, max_steps, prompt_config, verbose)

        print(f"  Agent finished in {agent_result['elapsed_seconds']}s, "
              f"submitted={agent_result['submitted']}")

        if agent_result["explanation"]:
            print(f"  Explanation: {agent_result['explanation']}")

        print(f"  Running tests...")
        test_result = run_tests(task_dir, workspace)

        passed = test_result["tests_passed"]
        print(f"  Tests: {'PASS' if passed else 'FAIL'}")

        tokens = extract_token_summary(agent_result["stdout"])

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
    parser.add_argument("--prompt-config", help="Path to prompt config YAML override")
    parser.add_argument("--verbose", action="store_true", help="Show agent thoughts and tool calls in real time")
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
        r = run_single_task(task_dir, args.model, args.max_steps, args.prompt_config, args.verbose)
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
