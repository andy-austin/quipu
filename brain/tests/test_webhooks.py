"""Tests for webhook trigger endpoints."""

import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient

from brain.dependencies import verify_user
from brain.server import app
from brain.webhooks import _verify_signature


@pytest.fixture
def client():
    app.dependency_overrides[verify_user] = lambda: "user-1"
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.clear()


class TestVerifySignature:
    def test_valid_signature(self):
        secret = "my-secret"
        body = b'{"message": "hello"}'
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        sig = f"sha256={expected}"
        assert _verify_signature(secret, body, sig) is True

    def test_invalid_signature(self):
        assert _verify_signature("secret", b"body", "sha256=wrong") is False

    def test_empty_signature(self):
        assert _verify_signature("secret", b"body", "") is False


class TestWebhookEndpoints:
    def test_register_webhook_no_mcp(self, client):
        resp = client.post(
            "/api/webhooks",
            json={"name": "test-hook", "agent": "chat"},
        )
        assert resp.status_code == 503

    def test_list_webhooks_no_mcp(self, client):
        resp = client.get("/api/webhooks")
        assert resp.status_code == 200
        assert resp.json() == {"webhooks": []}

    def test_delete_webhook_no_mcp(self, client):
        resp = client.delete("/api/webhooks/some-id")
        assert resp.status_code == 503

    def test_trigger_webhook_no_mcp(self, client):
        """Trigger endpoint is unauthenticated (uses HMAC) so no override needed."""
        resp = client.post(
            "/api/webhooks/some-id/trigger",
            json={"message": "hello"},
        )
        assert resp.status_code == 503


class TestWebhookTools:
    """Tests for hands-side webhook tools."""

    async def test_create_webhook(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"id": "wh-123"})
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=mock_conn)

        with patch(
            "hands.tools.webhook_tools.get_pool",
            AsyncMock(return_value=mock_pool),
        ):
            from hands.tools.webhook_tools import create_webhook

            result = await create_webhook("user-1", "my-hook", "chat")

        assert result["id"] == "wh-123"
        assert result["name"] == "my-hook"
        assert "secret" in result

    async def test_list_webhooks_empty(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=mock_conn)

        with patch(
            "hands.tools.webhook_tools.get_pool",
            AsyncMock(return_value=mock_pool),
        ):
            from hands.tools.webhook_tools import list_webhooks

            result = await list_webhooks("user-1")

        assert result == {"webhooks": []}

    async def test_delete_webhook(self):
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 1")
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_pool = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=mock_conn)

        with patch(
            "hands.tools.webhook_tools.get_pool",
            AsyncMock(return_value=mock_pool),
        ):
            from hands.tools.webhook_tools import delete_webhook

            result = await delete_webhook("user-1", "wh-123")

        assert result["deleted"] is True
