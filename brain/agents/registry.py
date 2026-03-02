"""Agent registry for pluggable vertical agent definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from brain.logging import log

AGENTS_DIR = Path(__file__).parent / "definitions"


@dataclass
class AgentDefinition:
    """A vertical agent definition."""

    name: str
    description: str = ""
    system_prompt: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    output_schema: str | None = None


# Built-in agent definitions
_BUILTIN_AGENTS: dict[str, AgentDefinition] = {
    "chat": AgentDefinition(
        name="chat",
        description="General-purpose conversational agent",
        system_prompt=(
            "You are a helpful AI assistant. You can use tools when needed "
            "to answer questions or accomplish tasks. Be concise and helpful."
        ),
    ),
    "researcher": AgentDefinition(
        name="researcher",
        description="Research agent that gathers and synthesizes information",
        system_prompt=(
            "You are a research agent. Your job is to thoroughly investigate topics "
            "by scraping websites, checking databases, and synthesizing findings. "
            "Always cite your sources and provide structured summaries."
        ),
        allowed_tools=["scrape_website", "check_database_freshness"],
    ),
    "data-collector": AgentDefinition(
        name="data-collector",
        description="Collects and persists structured data from web sources",
        system_prompt=(
            "You are a data collection agent. Scrape the given URLs, extract key data, "
            "and save the results to the database. Be thorough and systematic."
        ),
        allowed_tools=["scrape_website", "save_metadata", "check_database_freshness"],
    ),
}

_custom_agents: dict[str, AgentDefinition] = {}


def _load_yaml_agents() -> None:
    """Load agent definitions from YAML files in the definitions directory."""
    if not AGENTS_DIR.exists():
        return
    for path in AGENTS_DIR.glob("*.yaml"):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict) or "name" not in data:
                log.warning("invalid_agent_yaml", path=str(path))
                continue
            agent = AgentDefinition(
                name=data["name"],
                description=data.get("description", ""),
                system_prompt=data.get("system_prompt", ""),
                allowed_tools=data.get("allowed_tools", []),
                output_schema=data.get("output_schema"),
            )
            _custom_agents[agent.name] = agent
            log.info("loaded_agent_definition", name=agent.name, source=str(path))
        except Exception as e:
            log.error("agent_yaml_load_error", path=str(path), error=str(e))


def get_agent(name: str) -> AgentDefinition | None:
    """Look up an agent definition by name."""
    return _custom_agents.get(name) or _BUILTIN_AGENTS.get(name)


def list_agents() -> list[dict]:
    """Return all available agent definitions as dicts."""
    all_agents = {**_BUILTIN_AGENTS, **_custom_agents}
    return [{"name": a.name, "description": a.description} for a in all_agents.values()]


def register_agent(agent: AgentDefinition) -> None:
    """Register a custom agent definition at runtime."""
    _custom_agents[agent.name] = agent


# Load YAML definitions on import
_load_yaml_agents()
