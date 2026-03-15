"""
Agent configuration.

Two sources of config, each with a clear responsibility:

.env (secrets & connection):
    AGENT_API_KEY    — API key
    AGENT_BASE_URL   — custom API endpoint
    AGENT_MODEL      — litellm model ID

agent_config.yaml (agent behavior):
    system_template, instance_template — prompt templates
    step_limit — max agent steps
    tools — whitelist of enabled tools

Everything else (working_dir, verbose) comes from CLI args.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# --- paths relative to this file ---
_AGENT_DIR = Path(__file__).resolve().parent
_DEFAULT_CONFIG = _AGENT_DIR / "agent_config.yaml"
_PROMPTS_DIR = _AGENT_DIR / "prompts"

# SDK built-in tools that are controlled via Agent(include_default_tools=...)
_SDK_BUILTIN_TOOLS = {"think": "ThinkTool", "finish": "FinishTool"}

# Default tool set when nothing is specified in config
_DEFAULT_TOOLS = ["bash", "bash_session", "grep", "smart_read", "smart_editor", "submit", "think", "finish"]


def _resolve_api_key() -> str | None:
    """Resolve API key from environment."""
    return os.getenv("AGENT_API_KEY")


@dataclass
class AgentYamlConfig:
    """Behavioral settings loaded from agent_config.yaml."""

    system_template: str = "system_prompt.j2"
    instance_template: str = "{{task}}"
    step_limit: int = 30
    cost_limit: float = 0
    tools: list[str] = field(default_factory=lambda: list(_DEFAULT_TOOLS))

    @classmethod
    def load(cls, path: str | Path | None = None) -> "AgentYamlConfig":
        path = Path(path) if path else _DEFAULT_CONFIG
        if not path.exists():
            return cls()
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
        agent_cfg = raw.get("agent", {})
        return cls(
            system_template=agent_cfg.get("system_template", cls.system_template),
            instance_template=agent_cfg.get("instance_template", cls.instance_template),
            step_limit=agent_cfg.get("step_limit", cls.step_limit),
            cost_limit=agent_cfg.get("cost_limit", cls.cost_limit),
            tools=agent_cfg.get("tools", list(_DEFAULT_TOOLS)),
        )

    @property
    def system_prompt_path(self) -> str:
        """Absolute path to the system prompt Jinja2 template."""
        return str(_PROMPTS_DIR / self.system_template)

    def render_instance(self, task: str) -> str:
        """Render the instance template with the given task text."""
        return self.instance_template.replace("{{task}}", task)

    @property
    def custom_tool_names(self) -> list[str]:
        """Tool names that need Tool(name=...) instances (non-SDK-builtin)."""
        return [t for t in self.tools if t not in _SDK_BUILTIN_TOOLS]

    @property
    def include_default_tools(self) -> list[str]:
        """SDK class names for built-in tools that should be included."""
        return [
            _SDK_BUILTIN_TOOLS[t]
            for t in self.tools
            if t in _SDK_BUILTIN_TOOLS
        ]


@dataclass
class AgentConfig:
    """Full agent configuration. Assembled from .env + YAML + CLI args."""

    # --- from .env (secrets & connection) ---
    model: str = field(
        default_factory=lambda: os.getenv("AGENT_MODEL", "anthropic/claude-sonnet-4-6")
    )
    base_url: str | None = field(
        default_factory=lambda: os.getenv("AGENT_BASE_URL") or None
    )
    api_key: str | None = field(default_factory=_resolve_api_key)

    # --- from agent_config.yaml (behavior) ---
    yaml_config: AgentYamlConfig = field(default_factory=AgentYamlConfig.load)

    # --- from CLI args (runtime) ---
    max_steps: int | None = None  # None = use yaml_config.step_limit
    working_dir: str = field(default_factory=lambda: os.path.abspath("."))
    verbose: bool = True

    @property
    def effective_max_steps(self) -> int:
        """CLI --max-steps overrides YAML step_limit."""
        return self.max_steps if self.max_steps is not None else self.yaml_config.step_limit
