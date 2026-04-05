"""
Utility helpers shared across agent components.
"""

import json
from pathlib import Path

SUBMISSION_FILE = "SUBMISSION.json"


def read_submission(working_dir: Path) -> tuple[bool, str]:
    """Return (submitted, explanation) by reading SUBMISSION.json.

    submitted:
        True  — SUBMISSION.json exists (agent called submit tool)
        False — file absent (step_limit / cost_limit / error / timeout)
    explanation:
        value of "explanation" key from the JSON, or "" if absent/unparseable.
    """
    path = working_dir / SUBMISSION_FILE
    if not path.exists():
        return False, ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True, ""
    return True, data.get("explanation", "")
