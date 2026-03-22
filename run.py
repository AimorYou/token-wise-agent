"""
Entry point for the custom code agent (OpenHands SDK).

Usage:
    uv run run.py "Fix the failing tests"
    uv run run.py --list-tools
    uv run run.py --model anthropic/claude-opus-4-6 "task"
    uv run run.py --working-dir /path/to/project "task"
    uv run run.py --quiet "task"
    uv run run.py --agent-config path/to/config.yaml "task"

Config sources:
    .env                   — secrets & connection (AGENT_API_KEY, AGENT_BASE_URL, AGENT_MODEL)
    agent/agent_config.yaml — behavior (system_template, instance_template, step_limit, tools)
    CLI args               — runtime overrides (--model, --max-steps, --working-dir, --quiet)
"""

import argparse
import json
import sys
from pathlib import Path

from pydantic import SecretStr
from rich.console import Console

# OpenHands SDK
from openhands.sdk import Agent, LLM, LocalConversation
from openhands.sdk.conversation import get_agent_final_response
from openhands.sdk.tool import Tool
from openhands.sdk.conversation.visualizer import DefaultConversationVisualizer

# Register all tools (custom + bash_session wrapping TerminalTool)
import agent.tools  # noqa: F401

from agent.config import AgentConfig, AgentYamlConfig
from agent.token_tracker import TokenTracker, populate_from_llm_metrics


def build_tools(yaml_config: AgentYamlConfig) -> list[Tool]:
    """Build Tool instances from config's tool whitelist (non-SDK-builtin only)."""
    return [Tool(name=name) for name in yaml_config.custom_tool_names]


def main() -> None:
    parser = argparse.ArgumentParser(description="Custom code agent (OpenHands SDK)")
    parser.add_argument("task", nargs="?", help="Task for the agent to solve")
    parser.add_argument("--list-tools", action="store_true", help="List tools from config and exit")
    parser.add_argument("--model", help="Override model from .env")
    parser.add_argument("--base-url", help="Override base URL from .env")
    parser.add_argument("--api-key", help="Override API key from .env")
    parser.add_argument("--max-steps", type=int, help="Override step_limit from agent_config.yaml")
    parser.add_argument("--working-dir", help="Working directory (default: current dir)")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")
    parser.add_argument("--agent-config", metavar="YAML", help="Path to agent config YAML")
    args = parser.parse_args()

    # Build config: .env defaults + YAML + CLI overrides
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

    if not args.task:
        parser.print_help()
        sys.exit(1)

    if not config.api_key:
        console.print(
            "[red]Error: no API key found.\n"
            "Set AGENT_API_KEY in .env or pass --api-key.[/red]"
        )
        sys.exit(1)

    tools = build_tools(config.yaml_config)
    tracker = TokenTracker(model=config.model)

    llm_kwargs = dict(model=config.model, api_key=SecretStr(config.api_key))
    if config.base_url:
        llm_kwargs["base_url"] = config.base_url
    llm_kwargs.update(config.yaml_config.llm_params)

    agent = Agent(
        llm=LLM(**llm_kwargs),
        tools=tools,
        system_prompt_filename=config.yaml_config.system_prompt_path,
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
    try:
        conversation.send_message(rendered_task)
        conversation.run()
        final = get_agent_final_response(conversation.state.events)
    finally:
        populate_from_llm_metrics(tracker, agent)
        conversation.close()

    if final and not config.verbose:
        console.print(f"\n[bold green]Result:[/bold green] {final}")

    tracker.print_summary(console)

    # Write metrics to JSON file for programmatic consumption (e.g. benchmarks)
    metrics_path = Path(config.working_dir) / "METRICS.json"
    metrics_path.write_text(json.dumps(tracker.summary(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
