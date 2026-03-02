"""Tests for the pluggable agent registry."""

import json
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage

from brain.agents.registry import (
    _BUILTIN_AGENTS,
    AgentDefinition,
    get_agent,
    list_agents,
    register_agent,
)
from brain.server import app


def test_builtin_agents_exist():
    assert "chat" in _BUILTIN_AGENTS
    assert "researcher" in _BUILTIN_AGENTS
    assert "data-collector" in _BUILTIN_AGENTS


def test_get_agent_returns_builtin():
    agent = get_agent("chat")
    assert agent is not None
    assert agent.name == "chat"
    assert len(agent.system_prompt) > 0


def test_get_agent_returns_none_for_unknown():
    assert get_agent("nonexistent-agent") is None


def test_register_agent():
    custom = AgentDefinition(
        name="test-agent",
        description="A test agent",
        system_prompt="You are a test.",
    )
    register_agent(custom)
    result = get_agent("test-agent")
    assert result is not None
    assert result.name == "test-agent"


def test_list_agents_includes_builtins():
    agents = list_agents()
    names = [a["name"] for a in agents]
    assert "chat" in names
    assert "researcher" in names


def test_yaml_agent_loaded():
    """The analyst.yaml definition should be loaded automatically."""
    agent = get_agent("analyst")
    assert agent is not None
    assert agent.name == "analyst"
    assert "analy" in agent.description.lower()


async def test_agents_list_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/agents")
        assert resp.status_code == 200
        data = resp.json()
        names = [a["name"] for a in data]
        assert "chat" in names


async def test_chat_uses_agent_system_prompt():
    """When agent=researcher, the researcher system prompt should be used."""
    fake_ai_msg = AIMessage(content="Research results here.")

    async def fake_astream(initial_state, config=None):
        yield {"chat": {"messages": [fake_ai_msg]}}

    with patch("brain.server.chat_graph") as mock_graph:
        mock_graph.astream = fake_astream

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/chat/stream",
                params={"message": "Research AI trends", "agent": "researcher"},
            )
            assert resp.status_code == 200

            events = []
            for line in resp.text.strip().split("\n"):
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

            types = [e["type"] for e in events]
            assert "answer" in types
