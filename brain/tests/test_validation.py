"""Tests for Pydantic input validation on Brain endpoints."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from brain.server import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_missing_url_returns_422(client):
    async with client:
        resp = await client.get("/api/test/stream")
        assert resp.status_code == 422


async def test_invalid_url_returns_422(client):
    async with client:
        resp = await client.get("/api/test/stream", params={"url": "not-a-url"})
        assert resp.status_code == 422


async def test_valid_url_returns_200(client):
    with patch("brain.server.agent_graph") as mock_graph:

        async def fake_stream(*args, **kwargs):
            yield {"reasoning": {"messages": []}}

        mock_graph.astream = fake_stream
        async with client:
            resp = await client.get("/api/test/stream", params={"url": "https://example.com"})
            assert resp.status_code == 200


async def test_valid_url_with_model_returns_200(client):
    with patch("brain.server.agent_graph") as mock_graph:

        async def fake_stream(*args, **kwargs):
            yield {"reasoning": {"messages": []}}

        mock_graph.astream = fake_stream
        async with client:
            resp = await client.get(
                "/api/test/stream",
                params={"url": "https://example.com", "model": "gemini-2.0-flash"},
            )
            assert resp.status_code == 200
