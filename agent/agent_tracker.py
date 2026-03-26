"""
Agent metrics tracker.

Tracks all agent metrics in one place:
- Token usage (input/output/cache per LLM call)
- Cost estimation based on model pricing
- Tool call counts and errors
- LLM call count (steps)

Also provides populate_from_conversation() to extract tool metrics from events,
and make_token_callback() for OpenHands LocalConversation streaming.

Usage:
    tracker = AgentTracker(model="anthropic/claude-sonnet-4-6")
    # ... run agent ...
    populate_from_llm_metrics(tracker, agent)
    populate_from_events(tracker, conversation.state.events)
    tracker.print_summary()
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from rich.console import Console
from rich.table import Table


# Pricing per million tokens (USD).
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {
        "input": 3.0,
        "output": 15.0,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
    "claude-opus-4-6": {
        "input": 15.0,
        "output": 75.0,
        "cache_write": 18.75,
        "cache_read": 1.50,
    },
    "claude-haiku-4-5-20251001": {
        "input": 0.80,
        "output": 4.0,
        "cache_write": 1.0,
        "cache_read": 0.08,
    },
    "qwen/qwen3-coder-next": {
        "input": 0.489,
        "output": 1.174,
        "cache_write": 0.0,
        "cache_read": 0.0,
    },
}


@dataclass
class StepUsage:
    step: int
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

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
    def total_cache_write(self) -> int:
        return sum(s.cache_creation_input_tokens for s in self.steps)

    @property
    def total_cache_read(self) -> int:
        return sum(s.cache_read_input_tokens for s in self.steps)

    @property
    def total_cost(self) -> float:
        return sum(s.cost(self.model) for s in self.steps)

    def summary(self) -> dict:
        return {
            "model": self.model,
            "llm_calls": self.llm_calls,
            "total_input_tokens": self.total_input,
            "total_output_tokens": self.total_output,
            "total_cache_write_tokens": self.total_cache_write,
            "total_cache_read_tokens": self.total_cache_read,
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
        table.add_row("LLM calls", str(s["llm_calls"]))
        table.add_row("Total tool calls", str(s["total_tool_calls"]))
        table.add_row("Tool errors", str(s["tool_errors"]))
        table.add_row("", "")
        table.add_row("Input tokens", f"{s['total_input_tokens']:,}")
        table.add_row("Output tokens", f"{s['total_output_tokens']:,}")
        table.add_row("Cache write tokens", f"{s['total_cache_write_tokens']:,}")
        table.add_row("Cache read tokens", f"{s['total_cache_read_tokens']:,}")
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
    """Count tool calls and tool errors from conversation events."""
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


def make_token_callback(tracker: AgentTracker) -> Callable[[Any], None]:
    """
    Return a ConversationTokenCallbackType for OpenHands LocalConversation.

    Pass the result to LocalConversation(token_callbacks=[cb]).
    """
    step_counter = [0]

    def _on_token(chunk: Any) -> None:
        usage = getattr(chunk, "usage", None)
        if usage is None:
            raw = getattr(chunk, "raw_response", None) or {}
            usage = raw.get("usage") if isinstance(raw, dict) else None
        if usage is None:
            return

        def _get(obj, *attrs: str, default: int = 0) -> int:
            for attr in attrs:
                v = getattr(obj, attr, None) if not isinstance(obj, dict) else obj.get(attr)
                if v:
                    return int(v)
            return default

        step_counter[0] += 1
        tracker.record(
            step=step_counter[0],
            input_tokens=_get(usage, "prompt_tokens", "input_tokens"),
            output_tokens=_get(usage, "completion_tokens", "output_tokens"),
            cache_creation_input_tokens=_get(usage, "cache_creation_input_tokens"),
            cache_read_input_tokens=_get(usage, "cache_read_input_tokens"),
        )

    return _on_token
