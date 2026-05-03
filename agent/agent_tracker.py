"""
Agent metrics tracker.

Tracks token usage, cost, tool call counts per agent run.
Trajectory (full message log) is written to TRAJECTORY.traj.json
by agent/trajectory.py — not collected here.

Usage:
    tracker = AgentTracker(model="anthropic/claude-sonnet-4-6")
    token_cb = make_token_callback(tracker)
    # pass token_cb to LocalConversation
    # ... run agent ...
    populate_from_events(tracker, conversation.state.events)
    tracker.print_summary()
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from rich.console import Console
from rich.table import Table


def _load_pricing() -> dict[str, dict[str, float]]:
    path = Path(__file__).resolve().parent.parent / "configs" / "pricing.yaml"
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


# Pricing per million tokens (USD). Loaded from configs/pricing.yaml.
# Keys: model name WITHOUT provider prefix.
MODEL_PRICING: dict[str, dict[str, float]] = _load_pricing()


@dataclass
class StepUsage:
    step: int
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    def cost(self, model: str) -> float:
        parts = model.split("/")
        key = "/".join(parts[1:]) if len(parts) > 1 else model
        pricing = MODEL_PRICING.get(key, {})
        if not pricing:
            return 0.0
        return (
            self.input_tokens * pricing["input"] / 1_000_000
            + self.output_tokens * pricing["output"] / 1_000_000
            + self.cache_creation_input_tokens * pricing.get("cache_write", 0.0) / 1_000_000
            + self.cache_read_input_tokens * pricing.get("cache_read", 0.0) / 1_000_000
        )


@dataclass
class AgentTracker:
    model: str = "claude-sonnet-4-6"
    steps: list[StepUsage] = field(default_factory=list)
    total_tool_calls: int = 0
    tool_errors: int = 0
    latency: float = 0.0
    _start_time: float = field(default=0.0, repr=False)

    def start(self) -> None:
        self._start_time = time.time()

    def stop(self) -> None:
        if self._start_time:
            self.latency = round(time.time() - self._start_time, 1)

    def record(
        self,
        step: int,
        input_tokens: int,
        output_tokens: int,
        cache_creation_input_tokens: int = 0,
        cache_read_input_tokens: int = 0,
    ) -> StepUsage:
        usage = StepUsage(
            step=step,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_input_tokens=cache_creation_input_tokens,
            cache_read_input_tokens=cache_read_input_tokens,
        )
        self.steps.append(usage)
        return usage

    @property
    def llm_calls(self) -> int:
        return len(self.steps)

    @property
    def total_input(self) -> int:
        return sum(s.input_tokens for s in self.steps)

    @property
    def total_output(self) -> int:
        return sum(s.output_tokens for s in self.steps)

    @property
    def total_cost(self) -> float:
        return sum(s.cost(self.model) for s in self.steps)

    def summary(self) -> dict:
        return {
            "model": self.model,
            "latency": self.latency,
            "llm_calls": self.llm_calls,
            "total_input_tokens": self.total_input,
            "total_output_tokens": self.total_output,
            "total_cost_usd": round(self.total_cost, 6),
            "total_tool_calls": self.total_tool_calls,
            "tool_errors": self.tool_errors,
        }

    def print_summary(self, console: Optional[Console] = None) -> None:
        console = console or Console()
        table = Table(title="Agent Summary", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        s = self.summary()
        table.add_row("Model", s["model"])
        table.add_row("Latency", f"{s['latency']}s")
        table.add_row("LLM calls", str(s["llm_calls"]))
        table.add_row("Total tool calls", str(s["total_tool_calls"]))
        table.add_row("Tool errors", str(s["tool_errors"]))
        table.add_row("", "")
        table.add_row("Input tokens", f"{s['total_input_tokens']:,}")
        table.add_row("Output tokens", f"{s['total_output_tokens']:,}")
        table.add_row("", "")
        table.add_row("Total cost", f"${s['total_cost_usd']:.4f}")

        console.print(table)


def populate_from_llm_metrics(tracker: AgentTracker, agent: Any) -> None:
    """Read token usage from agent.llm.metrics.token_usages after conversation.run()."""
    try:
        usages = agent.llm.metrics.token_usages
    except AttributeError:
        return
    for i, usage in enumerate(usages, 1):
        tracker.record(
            step=i,
            input_tokens=getattr(usage, "prompt_tokens", 0),
            output_tokens=getattr(usage, "completion_tokens", 0),
            cache_creation_input_tokens=getattr(usage, "cache_write_tokens", 0),
            cache_read_input_tokens=getattr(usage, "cache_read_tokens", 0),
        )


def populate_from_events(tracker: AgentTracker, events: Any) -> None:
    """Count tool calls and errors from conversation events."""
    from openhands.sdk.event import ActionEvent, ObservationEvent

    total_tool_calls = 0
    tool_errors = 0
    for event in events:
        if isinstance(event, ActionEvent) and event.tool_name:
            total_tool_calls += 1
        if isinstance(event, ObservationEvent) and event.observation.is_error:
            tool_errors += 1
    tracker.total_tool_calls = total_tool_calls
    tracker.tool_errors = tool_errors


