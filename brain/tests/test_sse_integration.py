"""Integration test for Brain SSE streaming endpoint."""

import json
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage

from brain.server import app


async def test_sse_stream_returns_events():
    """Test that the /api/test/stream endpoint returns SSE events."""
    # Mock the graph to return a simple AI response
    fake_ai_msg = AIMessage(content="Here is the result.")

    async def fake_astream(initial_state, config=None):
        yield {"reasoning": {"messages": [fake_ai_msg]}}

    with patch("brain.server.agent_graph") as mock_graph:
        mock_graph.astream = fake_astream

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/test/stream", params={"url": "https://example.com"})
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]

            # Parse SSE events
            events = []
            for line in resp.text.strip().split("\n"):
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

            # Should have at least a reasoning event and a done event
            types = [e["type"] for e in events]
            assert "reasoning" in types
            assert "done" in types
