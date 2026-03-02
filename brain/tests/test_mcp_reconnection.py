"""Tests for MCP reconnection logic."""

from unittest.mock import AsyncMock, MagicMock, patch

from brain import server as srv


async def test_connect_mcp_success_first_attempt():
    mock_client_instance = MagicMock()
    mock_tool = MagicMock()
    mock_tool.name = "test_tool"
    mock_client_instance.get_tools = AsyncMock(return_value=[mock_tool])

    with (
        patch.object(srv, "_mcp_connected", False),
        patch("brain.server.MultiServerMCPClient", return_value=mock_client_instance),
        patch("brain.server.graph_module") as mock_graph,
    ):
        await srv._connect_mcp("http://localhost:8080/sse")
        assert srv._mcp_connected is True
        assert mock_graph.remote_mcp_tools == [mock_tool]


async def test_connect_mcp_retries_on_failure():
    mock_client_instance = MagicMock()
    mock_tool = MagicMock()
    mock_tool.name = "test_tool"
    # Fail twice, then succeed
    mock_client_instance.get_tools = AsyncMock(
        side_effect=[ConnectionError("fail"), ConnectionError("fail"), [mock_tool]]
    )

    with (
        patch.object(srv, "_mcp_connected", False),
        patch.object(srv, "MCP_RETRY_BASE_DELAY", 0.01),
        patch("brain.server.MultiServerMCPClient", return_value=mock_client_instance),
        patch("brain.server.graph_module"),
    ):
        await srv._connect_mcp("http://localhost:8080/sse")
        assert srv._mcp_connected is True
        assert mock_client_instance.get_tools.call_count == 3


async def test_connect_mcp_gives_up_after_max_retries():
    mock_client_instance = MagicMock()
    mock_client_instance.get_tools = AsyncMock(side_effect=ConnectionError("fail"))

    with (
        patch.object(srv, "_mcp_connected", False),
        patch.object(srv, "MCP_MAX_RETRIES", 2),
        patch.object(srv, "MCP_RETRY_BASE_DELAY", 0.01),
        patch("brain.server.MultiServerMCPClient", return_value=mock_client_instance),
        patch("brain.server.graph_module"),
    ):
        await srv._connect_mcp("http://localhost:8080/sse")
        assert srv._mcp_connected is False
        assert mock_client_instance.get_tools.call_count == 2


async def test_health_reports_mcp_status():
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=srv.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        data = resp.json()
        assert "mcp_connected" in data
        assert "tools_loaded" in data
