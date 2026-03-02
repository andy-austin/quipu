"""Tests for the Results API endpoints."""

from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient

from brain.dependencies import verify_user
from brain.server import app


async def test_runs_list_without_mcp_tool():
    """When list_runs MCP tool is not available, return empty."""
    app.dependency_overrides[verify_user] = lambda: "user-1"
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("brain.server._get_mcp_tool", return_value=None):
                resp = await client.get("/api/runs")
                assert resp.status_code == 200
                data = resp.json()
                assert data["runs"] == []
                assert data["total"] == 0
    finally:
        app.dependency_overrides.clear()


async def test_runs_list_with_mcp_tool():
    """When list_runs MCP tool is available, return its result."""
    app.dependency_overrides[verify_user] = lambda: "user-1"
    try:
        mock_tool = AsyncMock()
        mock_tool.ainvoke = AsyncMock(
            return_value='{"runs": [{"id": "r1", "agent": "chat"}], "total": 1}'
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("brain.server._get_mcp_tool", return_value=mock_tool):
                resp = await client.get("/api/runs")
                assert resp.status_code == 200
                data = resp.json()
                assert data["total"] == 1
    finally:
        app.dependency_overrides.clear()


async def test_runs_get_without_mcp_tool():
    """When get_run MCP tool is not available, return empty."""
    app.dependency_overrides[verify_user] = lambda: "user-1"
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("brain.server._get_mcp_tool", return_value=None):
                resp = await client.get("/api/runs/some-id")
                assert resp.status_code == 200
                assert resp.json() == {}
    finally:
        app.dependency_overrides.clear()
