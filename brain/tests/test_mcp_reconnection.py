"""Tests for MCP registry and reconnection logic."""

from unittest.mock import AsyncMock, MagicMock, patch

from brain.mcp_registry import MCPRegistry


async def test_registry_connect_success():
    mock_client_instance = MagicMock()
    mock_tool = MagicMock()
    mock_tool.name = "test_tool"
    mock_client_instance.get_tools = AsyncMock(return_value=[mock_tool])

    registry = MCPRegistry()
    with patch("brain.mcp_registry.MultiServerMCPClient", return_value=mock_client_instance):
        result = await registry.connect("test", "http://localhost:8080/sse")

    assert result is True
    assert registry.connected is True
    assert len(registry.tools) == 1
    assert registry.tools[0].name == "test_tool"


async def test_registry_connect_retries_on_failure():
    mock_client_instance = MagicMock()
    mock_tool = MagicMock()
    mock_tool.name = "test_tool"
    mock_client_instance.get_tools = AsyncMock(
        side_effect=[ConnectionError("fail"), ConnectionError("fail"), [mock_tool]]
    )

    registry = MCPRegistry()
    with (
        patch("brain.mcp_registry.MultiServerMCPClient", return_value=mock_client_instance),
        patch("brain.mcp_registry.MCP_RETRY_BASE_DELAY", 0.01),
    ):
        result = await registry.connect("test", "http://localhost:8080/sse")

    assert result is True
    assert mock_client_instance.get_tools.call_count == 3


async def test_registry_gives_up_after_max_retries():
    mock_client_instance = MagicMock()
    mock_client_instance.get_tools = AsyncMock(side_effect=ConnectionError("fail"))

    registry = MCPRegistry()
    with (
        patch("brain.mcp_registry.MultiServerMCPClient", return_value=mock_client_instance),
        patch("brain.mcp_registry.MCP_MAX_RETRIES", 2),
        patch("brain.mcp_registry.MCP_RETRY_BASE_DELAY", 0.01),
    ):
        result = await registry.connect("test", "http://localhost:8080/sse")

    assert result is False
    assert registry.connected is False
    assert mock_client_instance.get_tools.call_count == 2


async def test_registry_multiple_servers():
    mock_client = MagicMock()
    tool_a = MagicMock()
    tool_a.name = "tool_a"
    tool_b = MagicMock()
    tool_b.name = "tool_b"
    mock_client.get_tools = AsyncMock(side_effect=[[tool_a], [tool_b]])

    registry = MCPRegistry()
    with patch("brain.mcp_registry.MultiServerMCPClient", return_value=mock_client):
        await registry.connect("server-1", "http://s1:8080/sse")
        await registry.connect("server-2", "http://s2:8080/sse")

    assert len(registry.tools) == 2
    assert len(registry.servers) == 2
    assert registry.status["server-1"]["healthy"] is True
    assert registry.status["server-2"]["healthy"] is True


async def test_registry_deduplicates_tools():
    mock_client = MagicMock()
    tool = MagicMock()
    tool.name = "shared_tool"
    mock_client.get_tools = AsyncMock(return_value=[tool])

    registry = MCPRegistry()
    with patch("brain.mcp_registry.MultiServerMCPClient", return_value=mock_client):
        await registry.connect("server-1", "http://s1:8080/sse")
        await registry.connect("server-2", "http://s2:8080/sse")

    # Same tool name from two servers — should only appear once
    assert len(registry.tools) == 1


async def test_registry_connect_all_from_env():
    import json

    servers = [
        {"name": "s1", "url": "http://s1:8080/sse"},
        {"name": "s2", "url": "http://s2:8080/sse"},
    ]
    mock_client = MagicMock()
    tool = MagicMock()
    tool.name = "tool"
    mock_client.get_tools = AsyncMock(return_value=[tool])

    registry = MCPRegistry()
    with (
        patch("brain.mcp_registry.MultiServerMCPClient", return_value=mock_client),
        patch.dict("os.environ", {"MCP_SERVERS": json.dumps(servers)}),
    ):
        await registry.connect_all()

    assert len(registry.servers) == 2


async def test_health_endpoint_reports_servers():
    from httpx import ASGITransport, AsyncClient

    from brain import server as srv

    transport = ASGITransport(app=srv.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        data = resp.json()
        assert "mcp_connected" in data
        assert "tools_loaded" in data
        assert "servers" in data
