"""
Entry point for the custom code agent (OpenHands SDK).

Usage:
    uv run run.py "Fix the failing tests"
    uv run run.py --list-tools
    uv run run.py --disable bash "task"
    uv run run.py --model anthropic/claude-opus-4-6 "task"
    uv run run.py --model openai/gpt-4o "task"
    uv run run.py --model openai/llama3 --base-url http://localhost:11434/v1 "task"
    uv run run.py --quiet "task"
    uv run run.py --prompt-config path/to/config.yaml "task"

Environment variables (or .env file):
    ANTHROPIC_API_KEY    — for Anthropic models
    OPENAI_API_KEY       — for OpenAI / compatible models
    AGENT_API_KEY        — universal override (takes priority)
    AGENT_MODEL          — default: anthropic/claude-sonnet-4-6
    AGENT_BASE_URL       — custom API base URL (for OpenAI-compatible services)
    AGENT_MAX_STEPS      — default: 50
    AGENT_WORKING_DIR    — default: . (current directory)
    AGENT_VERBOSE        — default: true
    AGENT_DISABLED_TOOLS — comma-separated tool names to disable
"""

import argparse
import sys

from pydantic import SecretStr
from rich.console import Console

# OpenHands SDK
from openhands.sdk import Agent, LLM, LocalConversation
from openhands.sdk.conversation import get_agent_final_response
from openhands.sdk.tool import Tool, list_registered_tools

# Register OpenHands built-in tools
from openhands.tools.terminal.definition import TerminalTool  # noqa: F401
from openhands.sdk.conversation.visualizer import DefaultConversationVisualizer  # noqa: F401

# Register our custom tools (bash, grep, smart_read, submit)
import agent.tools  # noqa: F401

from agent.config import AgentConfig, PromptConfig
from agent.token_tracker import TokenTracker, populate_from_llm_metrics


def build_tools(config: AgentConfig) -> list[Tool]:
    """
    All tools available to the agent.

    Tool name = snake_case class name without '_tool' suffix:
      TerminalTool  → "terminal"   (OpenHands built-in: persistent bash session)
      BashTool      → "bash"       (custom: stateless subprocess, simpler)
      GrepTool      → "grep"       (custom: regex search with context lines)
      SmartReadTool → "smart_read" (custom: read file with optional line range)
      SubmitTool    → "submit"     (custom: signal task completion)

    Add Tool(name="your_tool") here when you add a new custom tool.
    """
    all_tools = [
        Tool(name="terminal"),    # persistent bash session (OpenHands built-in)
        Tool(name="bash"),        # stateless subprocess bash (custom)
        Tool(name="grep"),        # regex search with context (custom)
        Tool(name="smart_read"),  # file reader with line range (custom)
        Tool(name="submit"),      # signal task completion (custom)
    ]
    return [t for t in all_tools if t.name not in config.disabled_tools]


def main() -> None:
    parser = argparse.ArgumentParser(description="Custom code agent (OpenHands SDK)")
    parser.add_argument("task", nargs="?", help="Task for the agent to solve")
    parser.add_argument("--list-tools", action="store_true", help="List registered tools and exit")
    parser.add_argument("--disable", nargs="+", metavar="TOOL", help="Disable specific tools for this run")
    parser.add_argument("--model", help="litellm model ID (e.g. anthropic/claude-opus-4-6, openai/gpt-4o)")
    parser.add_argument("--base-url", help="Custom API base URL for OpenAI-compatible services")
    parser.add_argument("--api-key", help="API key override")
    parser.add_argument("--max-steps", type=int, help="Override max steps")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")
    parser.add_argument(
        "--prompt-config", metavar="YAML",
        help="Path to prompt config YAML (default: agent/prompt_config.yaml)",
    )
    args = parser.parse_args()

    config = AgentConfig()
    if args.prompt_config:
        config.prompts = PromptConfig.load(args.prompt_config)
    if args.model:
        config.model = args.model
    if args.base_url:
        config.base_url = args.base_url
    if args.max_steps:
        config.max_steps = args.max_steps
    else:
        config.max_steps = config.prompts.step_limit
    if args.quiet:
        config.verbose = False
    if args.disable:
        config.disabled_tools.extend(args.disable)

    console = Console()

    if args.list_tools:
        console.print("\n[bold]Registered tools:[/bold]")
        for name in list_registered_tools():
            active = name in [t.name for t in build_tools(config)]
            status = "[green]enabled[/green]" if active else "[red]disabled[/red]"
            console.print(f"  {status}  [bold]{name}[/bold]")
        sys.exit(0)

    if not args.task:
        parser.print_help()
        sys.exit(1)

    api_key = args.api_key or config.api_key
    if not api_key:
        provider = config.model.split("/")[0] if "/" in config.model else "unknown"
        console.print(
            f"[red]Error: no API key found for provider '{provider}'.\n"
            f"Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or AGENT_API_KEY.[/red]"
        )
        sys.exit(1)

    tools = build_tools(config)
    tracker = TokenTracker(model=config.model)

    llm_kwargs = dict(model=config.model, api_key=SecretStr(api_key))
    if config.base_url:
        llm_kwargs["base_url"] = config.base_url

    # Use our custom system prompt template (absolute path)
    agent = Agent(
        llm=LLM(**llm_kwargs),
        tools=tools,
        system_prompt_filename=config.prompts.system_prompt_path,
    )

    visualizer = DefaultConversationVisualizer if config.verbose else None
    
    rendered_task = config.prompts.render_instance(args.task)
    conversation = LocalConversation(
        agent=agent,
        workspace=config.working_dir,
        max_iteration_per_run=config.max_steps,
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


if __name__ == "__main__":
    main()
