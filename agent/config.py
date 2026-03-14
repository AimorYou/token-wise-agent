"""
Agent configuration loaded from environment variables / .env file + YAML prompt config.

Model ID format:  <provider>/<model-name>
  The provider is always the FIRST segment; model name is everything after it.

  Anthropic:          anthropic/claude-sonnet-4-6
  OpenAI:             openai/gpt-4o
  OpenAI-compatible:  openai/qwen/qwen3-coder-next  +  AGENT_BASE_URL=https://api.example.com/v1
                      openai/llama3                  +  AGENT_BASE_URL=http://localhost:11434/v1

  With a custom base URL, litellm strips "openai/" and sends the rest as the model name
  to the API (e.g. "qwen/qwen3-coder-next" → sent as-is to AGENT_BASE_URL).

API key resolution order:
    1. AGENT_API_KEY  (universal override)
    2. ANTHROPIC_API_KEY  (if provider == "anthropic")
    3. OPENAI_API_KEY     (if provider == "openai")
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# --- paths relative to this file ---
_AGENT_DIR = Path(__file__).resolve().parent
_DEFAULT_PROMPT_CONFIG = _AGENT_DIR / "prompt_config.yaml"
_PROMPTS_DIR = _AGENT_DIR / "prompts"


def _resolve_api_key(model: str) -> str | None:
    if key := os.getenv("AGENT_API_KEY"):
        return key
    provider = model.split("/")[0].lower() if "/" in model else ""
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_API_KEY")
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY")
    return os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")


@dataclass
class PromptConfig:
    """Prompt templates loaded from YAML config."""

    system_template: str = "system_prompt.j2"
    instance_template: str = "{{task}}"
    step_limit: int = 30
    cost_limit: float = 0

    @classmethod
    def load(cls, path: str | Path | None = None) -> "PromptConfig":
        path = Path(path) if path else _DEFAULT_PROMPT_CONFIG
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
        )

    @property
    def system_prompt_path(self) -> str:
        """Absolute path to the system prompt Jinja2 template."""
        return str(_PROMPTS_DIR / self.system_template)

    def render_instance(self, task: str) -> str:
        """Render the instance template with the given task text."""
        return self.instance_template.replace("{{task}}", task)


@dataclass
class AgentConfig:
    # litellm model ID: "anthropic/claude-sonnet-4-6", "openai/gpt-4o", etc.
    model: str = field(
        default_factory=lambda: os.getenv("AGENT_MODEL", "anthropic/claude-sonnet-4-6")
    )
    # Optional custom base URL — for OpenAI-compatible APIs (Ollama, vLLM, Groq, etc.)
    # Example: AGENT_BASE_URL=http://localhost:11434/v1
    base_url: str | None = field(
        default_factory=lambda: os.getenv("AGENT_BASE_URL") or None
    )
    max_steps: int = field(
        default_factory=lambda: int(os.getenv("AGENT_MAX_STEPS", "50"))
    )
    working_dir: str = field(
        default_factory=lambda: os.path.abspath(os.getenv("AGENT_WORKING_DIR", "."))
    )
    verbose: bool = field(
        default_factory=lambda: os.getenv("AGENT_VERBOSE", "true").lower() == "true"
    )
    # Comma-separated tool names to disable (e.g. "bash,grep")
    disabled_tools: list[str] = field(
        default_factory=lambda: [
            t.strip()
            for t in os.getenv("AGENT_DISABLED_TOOLS", "").split(",")
            if t.strip()
        ]
    )

    # Prompt configuration (loaded from YAML)
    prompts: PromptConfig = field(default_factory=PromptConfig.load)

    @property
    def api_key(self) -> str | None:
        return _resolve_api_key(self.model)
