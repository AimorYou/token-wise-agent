"""Unit tests for custom tools (no API calls needed)."""

import os
import tempfile

import pytest

# Ensure tools are registered
import agent.tools  # noqa: F401
from openhands.sdk.tool import list_registered_tools


# ---------------------------------------------------------------------------
# BashTool
# ---------------------------------------------------------------------------

from agent.tools.bash import BashAction, BashTool


def _run_bash(command: str, timeout: int | None = None):
    tool = BashTool.create()[0]
    return tool(BashAction(command=command, timeout=timeout))


def test_bash_success():
    obs = _run_bash("echo hello")
    assert not obs.is_error
    assert "hello" in obs.text
    assert obs.exit_code == 0


def test_bash_exit_code():
    obs = _run_bash("exit 42")
    assert obs.is_error
    assert obs.exit_code == 42


def test_bash_stderr_included():
    obs = _run_bash("echo err >&2; exit 0")
    assert "err" in obs.text


def test_bash_timeout():
    obs = _run_bash("sleep 60", timeout=1)
    assert obs.is_error
    assert "timed out" in obs.text.lower()


def test_bash_testbed_rewrite():
    """Commands referencing /testbed should be rewritten to working_dir."""
    with tempfile.TemporaryDirectory() as td:
        # Create a file in the temp dir
        with open(os.path.join(td, "hello.txt"), "w") as f:
            f.write("world")
        tool = BashTool.create(working_dir=td)[0]
        obs = tool(BashAction(command="cat /testbed/hello.txt"))
        assert not obs.is_error
        assert "world" in obs.text


def test_bash_description_field():
    """BashAction should accept an optional description field without error."""
    obs = _run_bash("echo ok")
    assert not obs.is_error
    # Also verify with explicit description
    tool = BashTool.create()[0]
    obs = tool(BashAction(command="echo ok", description="test command"))
    assert not obs.is_error
    assert "ok" in obs.text


# ---------------------------------------------------------------------------
# GrepTool
# ---------------------------------------------------------------------------

from agent.tools.grep import GrepAction, GrepTool


@pytest.fixture
def repo_dir():
    """Create a tiny fake repo for grep tests."""
    with tempfile.TemporaryDirectory() as d:
        (open(os.path.join(d, "a.py"), "w")).write(
            "def foo():\n    return 42\n\ndef bar():\n    pass\n"
        )
        (open(os.path.join(d, "b.py"), "w")).write(
            "# This file calls foo\nresult = foo()\n"
        )
        (open(os.path.join(d, "notes.txt"), "w")).write("foo is a function\n")
        yield d


def _run_grep(path, pattern, **kwargs):
    tool = GrepTool.create()[0]
    return tool(GrepAction(path=path, pattern=pattern, **kwargs))


def test_grep_finds_matches(repo_dir):
    obs = _run_grep(repo_dir, "def foo")
    assert not obs.is_error
    assert "def foo" in obs.text
    assert "a.py" in obs.text


def test_grep_include_filter(repo_dir):
    obs = _run_grep(repo_dir, "foo", include="*.py")
    assert not obs.is_error
    assert "a.py" in obs.text
    # notes.txt is excluded by filter
    assert "notes.txt" not in obs.text


def test_grep_context_lines(repo_dir):
    obs = _run_grep(repo_dir, "return 42", context_lines=1)
    # Should include the line before (def foo():)
    assert "def foo" in obs.text


def test_grep_no_matches(repo_dir):
    obs = _run_grep(repo_dir, "nonexistent_xyz_pattern")
    assert "No matches found" in obs.text


def test_grep_invalid_regex(repo_dir):
    obs = _run_grep(repo_dir, "[invalid(regex")
    assert obs.is_error


def test_grep_ignore_case(repo_dir):
    obs = _run_grep(repo_dir, "DEF FOO", ignore_case=True)
    assert "def foo" in obs.text


# ---------------------------------------------------------------------------
# SmartReaderTool
# ---------------------------------------------------------------------------

from agent.tools.smart_reader import SmartReaderAction, SmartReaderTool


@pytest.fixture
def sample_file():
    """Create a temporary file with 20 numbered lines."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for i in range(1, 21):
            f.write(f"line {i}\n")
        path = f.name
    yield path
    os.unlink(path)


def _run_smart_reader(**kwargs):
    tool = SmartReaderTool.create()[0]
    action = SmartReaderAction(**kwargs)
    return tool(action)


def test_smart_reader_full_file(sample_file):
    obs = _run_smart_reader(path=sample_file)
    assert not obs.is_error
    for i in range(1, 21):
        assert f"line {i}" in obs.text


def test_smart_reader_line_range(sample_file):
    obs = _run_smart_reader(path=sample_file, start_line=3, end_line=5)
    assert not obs.is_error
    assert "line 3" in obs.text
    assert "line 5" in obs.text
    assert "line 1" not in obs.text
    assert "line 6" not in obs.text


def test_smart_reader_start_only(sample_file):
    obs = _run_smart_reader(path=sample_file, start_line=18)
    assert not obs.is_error
    assert "line 18" in obs.text
    assert "line 20" in obs.text
    assert "line 17" not in obs.text


def test_smart_reader_missing_file():
    obs = _run_smart_reader(path="/nonexistent/file.py")
    assert obs.is_error
    assert "not found" in obs.text.lower()


def test_smart_reader_includes_line_numbers(sample_file):
    obs = _run_smart_reader(path=sample_file, start_line=1, end_line=3)
    assert " | " in obs.text


def test_smart_reader_focus_line(sample_file):
    """focus_line=10 with context=3 should show lines 7-13."""
    obs = _run_smart_reader(path=sample_file, focus_line=10, context=3)
    assert not obs.is_error
    assert "line 7" in obs.text
    assert "line 10" in obs.text
    assert "line 13" in obs.text
    assert "line 6" not in obs.text
    assert "line 14" not in obs.text


def test_smart_reader_focus_line_at_start(sample_file):
    """focus_line=1 with context=2 should show lines 1-3 (no negatives)."""
    obs = _run_smart_reader(path=sample_file, focus_line=1, context=2)
    assert not obs.is_error
    assert "line 1" in obs.text
    assert "line 3" in obs.text


def test_smart_reader_truncation():
    """Large file output should be truncated."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for i in range(1, 2001):
            f.write(f"{'x' * 50} line {i}\n")
        path = f.name
    try:
        obs = _run_smart_reader(path=path)
        assert "truncated" in obs.text.lower()
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# SmartEditorTool
# ---------------------------------------------------------------------------

from agent.tools.smart_editor import SmartEditorAction, _SmartEditorExecutor


@pytest.fixture
def editor_env():
    """Create a temp dir with a test file and a fake conversation."""
    with tempfile.TemporaryDirectory() as td:
        test_path = os.path.join(td, "src", "module.py")
        os.makedirs(os.path.dirname(test_path))
        with open(test_path, "w") as f:
            f.write("def add(a, b):\n    return a - b\n\ndef greet():\n    return 'hello'\n")

        class _WS:
            working_dir = td

        class _Conv:
            workspace = _WS()

        executor = _SmartEditorExecutor()
        yield td, executor, _Conv()


def test_editor_replace(editor_env):
    td, ex, conv = editor_env
    obs = ex(SmartEditorAction(command="replace", path="src/module.py",
                               old="return a - b", new="return a + b"), conv)
    assert not obs.is_error
    with open(os.path.join(td, "src/module.py")) as f:
        assert "return a + b" in f.read()


def test_editor_replace_ambiguous(editor_env):
    _, ex, conv = editor_env
    obs = ex(SmartEditorAction(command="replace", path="src/module.py",
                               old="return", new="yield"), conv)
    assert obs.is_error
    assert "2 times" in obs.text


def test_editor_replace_not_found(editor_env):
    _, ex, conv = editor_env
    obs = ex(SmartEditorAction(command="replace", path="src/module.py",
                               old="nonexistent_string", new="x"), conv)
    assert obs.is_error
    assert "not found" in obs.text.lower()


def test_editor_insert(editor_env):
    td, ex, conv = editor_env
    obs = ex(SmartEditorAction(command="insert", path="src/module.py",
                               line=1, text='    """Add two numbers."""'), conv)
    assert not obs.is_error
    with open(os.path.join(td, "src/module.py")) as f:
        content = f.read()
    assert '"""Add two numbers."""' in content
    # Original first line still present
    assert "def add(a, b):" in content


def test_editor_create(editor_env):
    td, ex, conv = editor_env
    obs = ex(SmartEditorAction(command="create", path="src/new.py",
                               content="# new file\n"), conv)
    assert not obs.is_error
    assert os.path.exists(os.path.join(td, "src/new.py"))


def test_editor_create_existing_fails(editor_env):
    _, ex, conv = editor_env
    obs = ex(SmartEditorAction(command="create", path="src/module.py",
                               content="overwrite"), conv)
    assert obs.is_error
    assert "already exists" in obs.text.lower()


def test_editor_delete(editor_env):
    td, ex, conv = editor_env
    obs = ex(SmartEditorAction(command="delete", path="src/module.py"), conv)
    assert not obs.is_error
    assert not os.path.exists(os.path.join(td, "src/module.py"))


def test_editor_undo_replace(editor_env):
    td, ex, conv = editor_env
    ex(SmartEditorAction(command="replace", path="src/module.py",
                         old="return a - b", new="return a + b"), conv)
    obs = ex(SmartEditorAction(command="undo", path="src/module.py"), conv)
    assert not obs.is_error
    with open(os.path.join(td, "src/module.py")) as f:
        assert "return a - b" in f.read()


def test_editor_undo_nothing(editor_env):
    _, ex, conv = editor_env
    obs = ex(SmartEditorAction(command="undo"), conv)
    assert obs.is_error
    assert "nothing to undo" in obs.text.lower()


def test_editor_patch(editor_env):
    td, ex, conv = editor_env
    patch = """\
*** Begin Patch
*** Update File: src/module.py
@@
-    return a - b
+    return a + b
*** End Patch"""
    obs = ex(SmartEditorAction(command="patch", diff=patch), conv)
    assert not obs.is_error
    with open(os.path.join(td, "src/module.py")) as f:
        assert "return a + b" in f.read()


def test_editor_path_outside_workdir(editor_env):
    _, ex, conv = editor_env
    obs = ex(SmartEditorAction(command="replace", path="../../etc/passwd",
                               old="x", new="y"), conv)
    assert obs.is_error
    assert "outside" in obs.text.lower()


# ---------------------------------------------------------------------------
# GlobTool
# ---------------------------------------------------------------------------

from agent.tools.glob import GlobAction, GlobTool, _GlobExecutor


def test_glob_finds_py_files():
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "src"))
        open(os.path.join(td, "src", "main.py"), "w").close()
        open(os.path.join(td, "src", "utils.py"), "w").close()
        open(os.path.join(td, "README.md"), "w").close()

        ex = _GlobExecutor(working_dir=td)
        obs = ex(GlobAction(pattern="**/*.py"))
        assert not obs.is_error
        assert "main.py" in obs.text
        assert "utils.py" in obs.text
        assert "README.md" not in obs.text


def test_glob_no_matches():
    with tempfile.TemporaryDirectory() as td:
        ex = _GlobExecutor(working_dir=td)
        obs = ex(GlobAction(pattern="**/*.xyz"))
        assert "No files matched" in obs.text


def test_glob_subdir():
    with tempfile.TemporaryDirectory() as td:
        sub = os.path.join(td, "pkg")
        os.makedirs(sub)
        open(os.path.join(sub, "a.py"), "w").close()

        ex = _GlobExecutor(working_dir=td)
        obs = ex(GlobAction(pattern="*.py", path="pkg"))
        assert not obs.is_error
        assert "a.py" in obs.text


def test_glob_bad_dir():
    with tempfile.TemporaryDirectory() as td:
        ex = _GlobExecutor(working_dir=td)
        obs = ex(GlobAction(pattern="*.py", path="nonexistent"))
        assert obs.is_error


# ---------------------------------------------------------------------------
# SubmitTool
# ---------------------------------------------------------------------------

from agent.tools.submit import SubmitAction, _SubmitExecutor


def test_submit_creates_json():
    with tempfile.TemporaryDirectory() as td:
        ex = _SubmitExecutor(working_dir=td)
        obs = ex(SubmitAction(explanation="Fixed the bug"))
        assert not obs.is_error
        import json
        data = json.loads(open(os.path.join(td, "SUBMISSION.json")).read())
        assert data["submitted"] is True
        assert data["explanation"] == "Fixed the bug"


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

def test_custom_tools_registered():
    registered = list_registered_tools()
    assert "smart_reader" in registered
    assert "smart_editor" in registered
    assert "bash" in registered
    assert "bash_session" in registered
    assert "glob" in registered
    assert "grep" in registered
    assert "submit" in registered


# ---------------------------------------------------------------------------
# AgentYamlConfig
# ---------------------------------------------------------------------------

from agent.config import AgentYamlConfig, _DEFAULT_CONFIG


def test_default_config_path():
    """Default config must live at configs/agent_config.yaml (not agent/)."""
    assert _DEFAULT_CONFIG.parts[-2] == "configs"
    assert _DEFAULT_CONFIG.name == "agent_config.yaml"


def test_default_config_loads():
    """configs/agent_config.yaml must exist and be loadable."""
    assert _DEFAULT_CONFIG.exists(), f"Config not found: {_DEFAULT_CONFIG}"
    cfg = AgentYamlConfig.load()
    assert cfg.step_limit > 0
    assert len(cfg.tools) > 0


def test_user_config_loads():
    """configs/agent_config_user.yaml must exist and be loadable."""
    from pathlib import Path
    user_cfg_path = _DEFAULT_CONFIG.parent / "agent_config_user.yaml"
    assert user_cfg_path.exists(), f"User config not found: {user_cfg_path}"
    cfg = AgentYamlConfig.load(user_cfg_path)
    assert "bash_session" in cfg.tools
    assert "think" in cfg.tools


# ---------------------------------------------------------------------------
# AgentTracker
# ---------------------------------------------------------------------------

from agent.agent_tracker import AgentTracker


def test_agent_tracker_record():
    tracker = AgentTracker(model="anthropic/claude-sonnet-4-6")
    tracker.record(step=1, input_tokens=100, output_tokens=50)
    tracker.record(step=2, input_tokens=200, output_tokens=80)

    assert tracker.total_input == 300
    assert tracker.total_output == 130
    assert tracker.llm_calls == 2


def test_agent_tracker_cost():
    tracker = AgentTracker(model="anthropic/claude-sonnet-4-6")
    tracker.record(step=1, input_tokens=1_000_000, output_tokens=0)
    # 1M input tokens at $3.45/M
    assert abs(tracker.total_cost - 3.45) < 0.01


def test_agent_tracker_model_prefix_stripped():
    """Cost lookup should work with 'anthropic/model' and 'model' alike."""
    t1 = AgentTracker(model="anthropic/claude-sonnet-4-6")
    t2 = AgentTracker(model="claude-sonnet-4-6")
    t1.record(step=1, input_tokens=1000, output_tokens=500)
    t2.record(step=1, input_tokens=1000, output_tokens=500)
    assert abs(t1.total_cost - t2.total_cost) < 1e-9


def test_agent_tracker_tool_metrics():
    tracker = AgentTracker(model="anthropic/claude-sonnet-4-6")
    tracker.total_tool_calls = 15
    tracker.tool_errors = 3
    s = tracker.summary()
    assert s["total_tool_calls"] == 15
    assert s["tool_errors"] == 3


def test_agent_tracker_populate_from_llm_metrics():
    """populate_from_llm_metrics should read token usage from agent.llm.metrics."""
    from agent.agent_tracker import populate_from_llm_metrics

    tracker = AgentTracker(model="anthropic/claude-sonnet-4-6")

    class FakeUsage:
        prompt_tokens = 100
        completion_tokens = 40
        cache_write_tokens = 0
        cache_read_tokens = 0

    class FakeMetrics:
        token_usages = [FakeUsage()]

    class FakeLLM:
        metrics = FakeMetrics()

    class FakeAgent:
        llm = FakeLLM()

    populate_from_llm_metrics(tracker, FakeAgent())
    assert tracker.total_input == 100
    assert tracker.total_output == 40
    assert tracker.llm_calls == 1
