"""
token-wise-agent CLI entry point.

Usage:
    twa                              # interactive mode
    twa "Fix the failing tests"      # one-shot mode
    twa --list-tools
    twa --model anthropic/claude-opus-4-6 "task"
    twa --working-dir /path/to/project "task"
    twa --quiet "task"
    twa --agent-config path/to/config.yaml "task"

Config sources:
    .env                        — secrets & connection (AGENT_API_KEY, AGENT_BASE_URL, AGENT_MODEL)
    agent/configs/agent_config.yaml — behavior (system_template, instance_template, step_limit, tools)
    CLI args                    — runtime overrides (--model, --max-steps, --working-dir, --quiet)
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")

from pydantic import SecretStr
from rich.console import Console
from rich.panel import Panel

# OpenHands SDK
from openhands.sdk import Agent, LLM, LocalConversation
from openhands.sdk.conversation import get_agent_final_response
from openhands.sdk.conversation.exceptions import ConversationRunError
from openhands.sdk.conversation.state import ConversationExecutionStatus
from openhands.sdk.tool import Tool
from openhands.sdk.conversation.visualizer import DefaultConversationVisualizer
from openhands.sdk.event.conversation_error import ConversationErrorEvent
from openhands.sdk.security.confirmation_policy import AlwaysConfirm, NeverConfirm

# Register all tools (custom + bash_session wrapping TerminalTool)
import agent.tools  # noqa: F401

from agent.config import AgentConfig, AgentYamlConfig, _DEFAULT_USER_CONFIG, USER_CONFIG_DIR
from agent.agent_tracker import AgentTracker, MODEL_PRICING, populate_from_llm_metrics, populate_from_events
from agent.utils import read_submission
from agent.trajectory import get_trajectory_path, get_last_trajectory_path, write_trajectory


_MAX_RECOVERY_ATTEMPTS = 3


def _build_llm_kwargs(config: AgentConfig) -> dict:
    """Build LLM constructor kwargs, injecting per-token pricing from MODEL_PRICING."""
    kwargs: dict = dict(model=config.model, api_key=SecretStr(config.api_key))
    if config.base_url:
        kwargs["base_url"] = config.base_url
    kwargs.update(config.yaml_config.llm_params)

    model_parts = config.model.split("/")
    model_key = "/".join(model_parts[1:]) if len(model_parts) > 1 else config.model
    pricing = MODEL_PRICING.get(model_key, {})
    if pricing:
        kwargs["input_cost_per_token"] = pricing["input"] / 1_000_000
        kwargs["output_cost_per_token"] = pricing["output"] / 1_000_000
    return kwargs


def interactive_mode(config: AgentConfig, console: Console) -> None:
    """Persistent interactive chat session with the agent."""
    if not config.api_key:
        env_path = USER_CONFIG_DIR / ".env"
        console.print(
            f"[red]Error: no API key found.[/red]\n\n"
            f"Create [bold]{env_path}[/bold] with:\n"
            f"  [dim]AGENT_API_KEY=sk-...[/dim]\n"
            f"  [dim]AGENT_MODEL=anthropic/claude-sonnet-4-6  # optional[/dim]\n\n"
            f"Or pass it directly: [bold]twa --api-key sk-...[/bold]"
        )
        sys.exit(1)

    tools = build_tools(config.yaml_config)
    agent = Agent(
        llm=LLM(**_build_llm_kwargs(config)),
        tools=tools,
        system_prompt_filename=config.yaml_config.system_prompt_path,
        include_default_tools=config.yaml_config.include_default_tools,
    )

    conversation = LocalConversation(
        agent=agent,
        workspace=config.working_dir,
        max_iteration_per_run=config.effective_max_steps,
        visualizer=DefaultConversationVisualizer,
    )

    console.print()
    console.print(Panel(
        f"[bold white]Token-Wise Agent[/bold white]\n\n"
        f"  [dim]Model    [/dim]  {config.model}\n"
        f"  [dim]Workspace[/dim]  {config.working_dir}\n"
        f"  [dim]Steps    [/dim]  {config.effective_max_steps} per turn\n\n"
        f"[dim]/confirm — toggle confirmation mode · exit or Ctrl+C to quit[/dim]",
        border_style="cyan",
        title="[bold cyan]◆ Interactive Mode[/bold cyan]",
        padding=(1, 2),
    ))
    console.print()

    tracker = AgentTracker(model=config.model)
    tracker.start()
    prev_cost = 0.0
    confirm_state = False

    while True:
        if confirm_state:
            mode_hint = "[yellow]Confirmation mode[/yellow][dim] (type /auto to switch)[/dim]"
        else:
            mode_hint = "[green]Auto mode[/green][dim] (type /confirm to switch)[/dim]"
        prompt = f"[bold cyan]You[/bold cyan] ({mode_hint}) [dim]›[/dim] "
        try:
            user_input = console.input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "q", "/exit", "/quit"}:
            console.print("[dim]Goodbye![/dim]")
            break
        if user_input.lower() == "/confirm":
            confirm_state = True
            conversation.set_confirmation_policy(AlwaysConfirm())
            console.print("[dim]  Switched to confirmation mode.[/dim]\n")
            continue
        if user_input.lower() == "/auto":
            confirm_state = False
            conversation.set_confirmation_policy(NeverConfirm())
            console.print("[dim]  Switched to auto mode.[/dim]\n")
            continue

        console.print()
        try:
            conversation.send_message(user_input)
            while True:
                run_with_recovery(conversation)
                if (
                    conversation.state.execution_status
                    == ConversationExecutionStatus.WAITING_FOR_CONFIRMATION
                ):
                    try:
                        feedback = console.input(
                            "[bold yellow]  ›[/bold yellow] [dim]Enter to approve, or type feedback to reject:[/dim] "
                        ).strip()
                    except (KeyboardInterrupt, EOFError):
                        conversation.reject_pending_actions("User interrupted")
                        break
                    if feedback:
                        conversation.reject_pending_actions(feedback)
                else:
                    break
            final = get_agent_final_response(conversation.state.events)
        except Exception as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}\n")
            continue

        populate_from_llm_metrics(tracker, agent)
        populate_from_events(tracker, conversation.state.events)

        if final:
            console.print(Panel(
                final,
                title="[bold green]Agent[/bold green]",
                border_style="green",
                padding=(1, 2),
            ))

        summary = tracker.summary()
        cost = summary.get("cost_usd", 0.0)
        turn_cost = cost - prev_cost
        prev_cost = cost
        console.print(f"\n[dim]  ${turn_cost:.4f} this turn · ${cost:.4f} total[/dim]\n")

    tracker.stop()


def run_with_recovery(conversation: LocalConversation) -> None:
    """Run conversation, recovering from transient ConversationRunErrors."""
    for attempt in range(_MAX_RECOVERY_ATTEMPTS):
        try:
            conversation.run()
            return
        except ConversationRunError as exc:
            if attempt + 1 >= _MAX_RECOVERY_ATTEMPTS:
                raise
            cause = str(exc.__cause__ or exc)
            conversation.reject_pending_actions(f"Tool call failed: {cause}")
            with conversation._state:
                conversation._state.execution_status = ConversationExecutionStatus.IDLE
            conversation.send_message(
                f"[SYSTEM ERROR] The previous tool call crashed the runtime: {cause}. "
                "This is a transient error. Please retry your last action carefully, "
                "ensuring all tool arguments are valid."
            )


def build_tools(yaml_config: AgentYamlConfig) -> list[Tool]:
    """Build Tool instances from config's tool whitelist (non-SDK-builtin only)."""
    return [Tool(name=name) for name in yaml_config.custom_tool_names]


_ENV_TEMPLATE = """\
# Token-Wise Agent — connection settings
# Docs: https://github.com/AimorYou/token-wise-agent

AGENT_API_KEY=           # Required: your API key

# AGENT_MODEL=anthropic/claude-sonnet-4-6   # optional: model to use
# AGENT_BASE_URL=                            # optional: custom API endpoint
"""

_CONFIG_TEMPLATE = """\
# Token-Wise Agent — interactive mode settings
# Remove the leading '#' to override a value.

agent:
  # system_template: "system_prompt_user.j2"
  llm_params:
    temperature: 0.5
  step_limit: 50
  tools:
    - bash
    - glob
    - grep
    - smart_reader
    - smart_editor
    - think
"""


def _ensure_user_config_dir() -> None:
    """Create ~/.config/token-wise-agent/ with template files on first run."""
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    env_path = USER_CONFIG_DIR / ".env"
    config_path = USER_CONFIG_DIR / "agent_config_user.yaml"
    if not env_path.exists():
        env_path.write_text(_ENV_TEMPLATE)
    if not config_path.exists():
        config_path.write_text(_CONFIG_TEMPLATE)


def _edit_config(target: str, console: Console) -> None:
    """Open a config file in $EDITOR."""
    import subprocess
    files = {
        "env": USER_CONFIG_DIR / ".env",
        "config": USER_CONFIG_DIR / "agent_config_user.yaml",
    }
    path = files[target]
    _ensure_user_config_dir()
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "nano"
    console.print(f"[dim]Opening {path} in {editor}…[/dim]")
    subprocess.run([editor, str(path)])


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="twa",
        description="Token-Wise Agent — an AI coding assistant",
    )
    subparsers = parser.add_subparsers(dest="command")
    edit_parser = subparsers.add_parser("edit", help="Edit configuration files")
    edit_parser.add_argument(
        "file", nargs="?", choices=["env", "config"], default="env",
        help="Which file to edit: env (default) or config",
    )

    parser.add_argument("task", nargs="?", help="Task for the agent to solve")
    parser.add_argument(
        "--interactive", "-i", action="store_true",
        help="Start an interactive chat session (default when no task is given)",
    )
    parser.add_argument("--list-tools", action="store_true", help="List tools from config and exit")
    parser.add_argument("--model", help="Override model from .env")
    parser.add_argument("--base-url", help="Override base URL from .env")
    parser.add_argument("--api-key", help="Override API key from .env")
    parser.add_argument("--max-steps", type=int, help="Override step_limit from agent_config.yaml")
    parser.add_argument("--working-dir", help="Working directory (default: current dir)")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")
    parser.add_argument("--agent-config", metavar="YAML", help="Path to agent config YAML")
    parser.add_argument("--run-id", help="Run identifier (shared across a benchmark batch)")
    parser.add_argument("--task-id", help="Task identifier (e.g. task-001-fix-foo)")
    parser.add_argument(
        "--save-only-last-traj", action=argparse.BooleanOptionalAction, default=True,
        help="If true (default), overwrite last_twa_run.traj.json; if false, save to {run_id}/{task_id}.traj.json",
    )
    parser.add_argument(
        "--traj-output", metavar="PATH",
        help="Explicit path for the trajectory file (overrides --save-only-last-traj logic)",
    )
    args = parser.parse_args()

    _ensure_user_config_dir()

    if args.command == "edit":
        console = Console()
        _edit_config(args.file, console)
        return

    config = AgentConfig()
    if args.agent_config:
        config.yaml_config = AgentYamlConfig.load(args.agent_config)
    if args.model:
        config.model = args.model
    if args.base_url:
        config.base_url = args.base_url
    if args.api_key:
        config.api_key = args.api_key
    if args.max_steps:
        config.max_steps = args.max_steps
    if args.working_dir:
        config.working_dir = args.working_dir
    if args.quiet:
        config.verbose = False

    console = Console()

    if args.list_tools:
        yaml_cfg = config.yaml_config
        console.print(f"\n[bold]Tools from config:[/bold]")
        for name in yaml_cfg.tools:
            console.print(f"  [green]●[/green]  [bold]{name}[/bold]")
        console.print(f"\n  Custom tools: {yaml_cfg.custom_tool_names}")
        console.print(f"  SDK built-in: {yaml_cfg.include_default_tools}")
        sys.exit(0)

    if args.interactive or not args.task:
        if not args.agent_config:
            config.yaml_config = AgentYamlConfig.load(_DEFAULT_USER_CONFIG)
        interactive_mode(config, console)
        return

    if not config.api_key:
        env_path = USER_CONFIG_DIR / ".env"
        console.print(
            f"[red]Error: no API key found.[/red]\n\n"
            f"Create [bold]{env_path}[/bold] with:\n"
            f"  [dim]AGENT_API_KEY=sk-...[/dim]\n\n"
            f"Or pass it directly: [bold]twa --api-key sk-...[/bold]"
        )
        sys.exit(1)

    run_id = args.run_id or f"run_{datetime.now():%Y-%m-%d_%H-%M-%S}"
    task_id = args.task_id or "task"

    tools = build_tools(config.yaml_config)
    tracker = AgentTracker(model=config.model)

    system_prompt_path = config.yaml_config.system_prompt_path
    try:
        system_prompt = Path(system_prompt_path).read_text(encoding="utf-8")
    except OSError:
        system_prompt = system_prompt_path

    agent = Agent(
        llm=LLM(**_build_llm_kwargs(config)),
        tools=tools,
        system_prompt_filename=system_prompt_path,
        include_default_tools=config.yaml_config.include_default_tools,
    )

    visualizer = DefaultConversationVisualizer if config.verbose else None
    rendered_task = config.yaml_config.render_instance(args.task)

    conversation = LocalConversation(
        agent=agent,
        workspace=config.working_dir,
        max_iteration_per_run=config.effective_max_steps,
        visualizer=visualizer,
    )
    exit_status = "submitted"
    started_at = datetime.now().astimezone().isoformat()
    tracker.start()
    try:
        conversation.send_message(rendered_task)
        run_with_recovery(conversation)
        final = get_agent_final_response(conversation.state.events)
    except Exception as exc:
        exit_status = type(exc).__name__
        final = None
    finally:
        tracker.stop()
        populate_from_llm_metrics(tracker, agent)
        populate_from_events(tracker, conversation.state.events)
        conversation.close()

    if final and not config.verbose:
        console.print(f"\n[bold green]Result:[/bold green] {final}")
    tracker.print_summary(console)

    working_dir = Path(config.working_dir)
    submitted, submission_content = read_submission(working_dir)
    if submitted:
        exit_status = "submitted"
    elif any(
        isinstance(e, ConversationErrorEvent) and e.code == "MaxIterationsReached"
        for e in conversation.state.events
    ):
        exit_status = "max_steps"

    metrics_path = working_dir / "METRICS.json"
    metrics_path.write_text(json.dumps(tracker.summary(), indent=2, ensure_ascii=False))

    if args.traj_output:
        traj_path = Path(args.traj_output)
    elif args.save_only_last_traj:
        traj_path = get_last_trajectory_path()
    else:
        traj_path = get_trajectory_path(run_id, task_id)
    try:
        write_trajectory(
            path=traj_path,
            run_id=run_id,
            task_id=task_id,
            started_at=started_at,
            tracker=tracker,
            events=conversation.state.events,
            config=config,
            rendered_task=rendered_task,
            system_prompt=system_prompt,
            exit_status=exit_status,
            submission_content=submission_content,
        )
        console.print(f"\n[dim]Trajectory saved → {traj_path}[/dim]")
    except Exception as exc:
        console.print(f"\n[red]Failed to save trajectory: {exc}[/red]")
