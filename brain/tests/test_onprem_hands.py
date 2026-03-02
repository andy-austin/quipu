"""Tests for on-prem Hands — user server registration and token auth."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from brain.dependencies import verify_user
from brain.server import app
from hands.auth import verify_token


@pytest.fixture
def client():
    app.dependency_overrides[verify_user] = lambda: "user-1"
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.clear()


class TestTokenAuth:
    def test_verify_token_no_config(self):
        with patch("hands.auth._AUTH_TOKEN", ""):
            assert verify_token("anything") is True

    def test_verify_token_valid(self):
        with patch("hands.auth._AUTH_TOKEN", "secret-123"):
            assert verify_token("secret-123") is True

    def test_verify_token_invalid(self):
        with patch("hands.auth._AUTH_TOKEN", "secret-123"):
            assert verify_token("wrong") is False


class TestBrainServerEndpoints:
    def test_register_server_no_mcp(self, client):
        resp = client.post(
            "/api/servers",
            params={"name": "my-hands", "url": "http://my-server:8080/sse"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"error": "Server registration not available"}

    def test_list_servers_no_mcp(self, client):
        resp = client.get("/api/servers")
        assert resp.status_code == 200
        assert resp.json() == {"servers": []}

    def test_delete_server_no_mcp(self, client):
        resp = client.delete("/api/servers/some-id")
        assert resp.status_code == 200
        assert resp.json() == {"error": "Server management not available"}


class TestUserServerTools:
    async def test_register_user_server(self):
        ts = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"id": "srv-1", "created_at": ts})
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=mock_conn)

        with patch(
            "hands.tools.user_server_tools.get_pool",
            AsyncMock(return_value=mock_pool),
        ):
            from hands.tools.user_server_tools import register_user_server

            result = await register_user_server("user-1", "my-hands", "http://my-server:8080/sse")

        assert result["id"] == "srv-1"
        assert result["name"] == "my-hands"

    async def test_list_user_servers_empty(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=mock_conn)

        with patch(
            "hands.tools.user_server_tools.get_pool",
            AsyncMock(return_value=mock_pool),
        ):
            from hands.tools.user_server_tools import list_user_servers

            result = await list_user_servers("user-1")

        assert result == {"servers": []}

    async def test_delete_user_server(self):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 1")
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=mock_conn)

        with patch(
            "hands.tools.user_server_tools.get_pool",
            AsyncMock(return_value=mock_pool),
        ):
            from hands.tools.user_server_tools import delete_user_server

            result = await delete_user_server("user-1", "srv-1")

        assert result["deleted"] is True
