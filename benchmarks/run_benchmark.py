"""
SWE-Bench-style benchmark runner.

For each task, runs pytest in the task directory and reports pass/fail.
Designed to verify that:
  - All tests FAIL before the agent fixes the bug
  - All tests PASS after the agent fixes the bug

Usage:
    python benchmarks/run_benchmark.py              # run all tasks
    python benchmarks/run_benchmark.py task_001      # run specific task
"""

import subprocess
import sys
from pathlib import Path

TASKS_DIR = Path(__file__).parent / "tasks"


def run_task(task_dir: Path) -> dict:
    """Run pytest for a single task and return results."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "tests/"],
        cwd=task_dir,
        capture_output=True,
        text=True,
    )
    return {
        "task": task_dir.name,
        "returncode": result.returncode,
        "passed": result.returncode == 0,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main():
    filter_name = sys.argv[1] if len(sys.argv) > 1 else None

    task_dirs = sorted(TASKS_DIR.iterdir())
    task_dirs = [d for d in task_dirs if d.is_dir()]

    if filter_name:
        task_dirs = [d for d in task_dirs if filter_name in d.name]

    if not task_dirs:
        print("No tasks found.")
        sys.exit(1)

    results = []
    for task_dir in task_dirs:
        print(f"\n{'='*60}")
        print(f"Running: {task_dir.name}")
        print(f"{'='*60}")

        r = run_task(task_dir)
        results.append(r)

        status = "PASS" if r["passed"] else "FAIL"
        print(f"Status: {status}")
        if not r["passed"]:
            print(r["stdout"][-500:] if len(r["stdout"]) > 500 else r["stdout"])

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['task']}")

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"\n{passed}/{total} tasks passed")


if __name__ == "__main__":
    main()
