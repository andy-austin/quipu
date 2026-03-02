"""Tests for conversation persistence in chat streaming."""

import json
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage

from brain.server import app


async def test_chat_stream_includes_conversation_id_in_done():
    """Test that conversation_id is included in done event when provided."""
    fake_ai_msg = AIMessage(content="Hello!")

    async def fake_astream(initial_state, config=None):
        yield {"chat": {"messages": [fake_ai_msg]}}

    with patch("brain.server.chat_graph") as mock_graph:
        mock_graph.astream = fake_astream

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/chat/stream",
                params={"message": "Hello", "conversation_id": "conv-123"},
            )
            assert resp.status_code == 200

            events = []
            for line in resp.text.strip().split("\n"):
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

            done_events = [e for e in events if e["type"] == "done"]
            assert len(done_events) == 1
            assert done_events[0]["conversation_id"] == "conv-123"


async def test_chat_stream_no_conversation_id_omits_from_done():
    """Test that done event has no conversation_id when not provided."""
    fake_ai_msg = AIMessage(content="Hello!")

    async def fake_astream(initial_state, config=None):
        yield {"chat": {"messages": [fake_ai_msg]}}

    with patch("brain.server.chat_graph") as mock_graph:
        mock_graph.astream = fake_astream

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/chat/stream", params={"message": "Hello"})

            events = []
            for line in resp.text.strip().split("\n"):
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

            done_events = [e for e in events if e["type"] == "done"]
            assert "conversation_id" not in done_events[0]
