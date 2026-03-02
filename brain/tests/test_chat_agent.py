"""Tests for the general-purpose chat agent."""

import json
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage

from brain.chat_graph import DEFAULT_SYSTEM_PROMPT, build_chat_graph, should_continue
from brain.server import app


def test_should_continue_returns_tools_when_tool_calls():
    msg = AIMessage(content="")
    msg.tool_calls = [{"id": "1", "name": "scrape_website", "args": {}}]
    state = {"messages": [msg]}  # type: ignore[typeddict-item]
    assert should_continue(state) == "execute_tools"


def test_should_continue_returns_end_when_no_tool_calls():
    msg = AIMessage(content="Hello!")
    state = {"messages": [msg]}  # type: ignore[typeddict-item]
    assert should_continue(state) == "__end__"


def test_build_chat_graph_compiles():
    graph = build_chat_graph()
    assert graph is not None


def test_default_system_prompt_exists():
    assert len(DEFAULT_SYSTEM_PROMPT) > 0


async def test_chat_stream_endpoint():
    """Test the /api/chat/stream endpoint returns SSE events."""
    fake_ai_msg = AIMessage(content="Hello, how can I help?")

    async def fake_astream(initial_state, config=None):
        yield {"chat": {"messages": [fake_ai_msg]}}

    with patch("brain.server.chat_graph") as mock_graph:
        mock_graph.astream = fake_astream

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/chat/stream",
                params={"message": "Hello", "agent": "chat"},
            )
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]

            events = []
            for line in resp.text.strip().split("\n"):
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

            types = [e["type"] for e in events]
            assert "answer" in types
            assert "done" in types


async def test_chat_stream_with_custom_system_prompt():
    """Test that custom system_prompt is accepted."""
    fake_ai_msg = AIMessage(content="I am a pirate!")

    async def fake_astream(initial_state, config=None):
        yield {"chat": {"messages": [fake_ai_msg]}}

    with patch("brain.server.chat_graph") as mock_graph:
        mock_graph.astream = fake_astream

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/chat/stream",
                params={
                    "message": "Who are you?",
                    "system_prompt": "You are a pirate.",
                },
            )
            assert resp.status_code == 200


async def test_agent_selection_scrape():
    """Test that agent=scrape routes to the scraping graph."""
    fake_ai_msg = AIMessage(content="Scraped data.")

    async def fake_astream(initial_state, config=None):
        yield {"reasoning": {"messages": [fake_ai_msg]}}

    with patch("brain.server.agent_graph") as mock_graph:
        mock_graph.astream = fake_astream

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/chat/stream",
                params={
                    "message": "Scrape example.com",
                    "agent": "scrape",
                    "url": "https://example.com",
                },
            )
            assert resp.status_code == 200
