"""Tests for hands.tools.notification_tools — email, Slack, webhook notifications."""

from unittest.mock import AsyncMock, patch

import pytest

from hands.tools import notification_tools
from hands.tools.notification_tools import (
    send_email,
    send_slack_message,
    send_webhook,
)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Clear rate limit state between tests."""
    notification_tools._user_timestamps.clear()
    yield
    notification_tools._user_timestamps.clear()


def _mock_httpx(status_code, headers=None, text="ok"):
    """Create a patched httpx.AsyncClient context returning a mock response."""
    mock_resp = AsyncMock()
    mock_resp.status_code = status_code
    mock_resp.headers = headers or {}
    mock_resp.text = text

    patcher = patch("hands.tools.notification_tools.httpx.AsyncClient")
    mock_cls = patcher.start()
    instance = mock_cls.return_value
    instance.__aenter__ = AsyncMock(return_value=instance)
    instance.__aexit__ = AsyncMock(return_value=False)
    instance.post = AsyncMock(return_value=mock_resp)
    return patcher, instance


class TestRateLimiting:
    async def test_rate_limit_exceeded(self):
        with patch.object(notification_tools, "_RATE_LIMIT", 2):
            patcher, _ = _mock_httpx(200)
            try:
                await send_webhook("user-1", "https://example.com/hook", {"data": "1"})
                await send_webhook("user-1", "https://example.com/hook", {"data": "2"})
                with pytest.raises(ValueError, match="Rate limit exceeded"):
                    await send_webhook("user-1", "https://example.com/hook", {"data": "3"})
            finally:
                patcher.stop()

    async def test_separate_users_not_affected(self):
        with patch.object(notification_tools, "_RATE_LIMIT", 1):
            patcher, _ = _mock_httpx(200)
            try:
                await send_webhook("user-1", "https://example.com/hook", {})
                await send_webhook("user-2", "https://example.com/hook", {})
            finally:
                patcher.stop()


class TestSendEmail:
    async def test_send_email_no_api_key(self):
        with patch.dict("os.environ", {"SENDGRID_API_KEY": ""}, clear=False):
            result = await send_email("user-1", "test@example.com", "Hi", "Body")
        assert result["status"] == "error"
        assert "not configured" in result["error"]

    async def test_send_email_success(self):
        patcher, _ = _mock_httpx(202, headers={"X-Message-Id": "msg-123"})
        try:
            with patch.dict("os.environ", {"SENDGRID_API_KEY": "sg-key"}, clear=False):
                result = await send_email("user-1", "test@example.com", "Hi", "Body")
        finally:
            patcher.stop()
        assert result["status"] == "sent"
        assert result["message_id"] == "msg-123"

    async def test_send_email_failure(self):
        patcher, _ = _mock_httpx(400, text="Bad Request")
        try:
            with patch.dict("os.environ", {"SENDGRID_API_KEY": "sg-key"}, clear=False):
                result = await send_email("user-1", "test@example.com", "Hi", "Body")
        finally:
            patcher.stop()
        assert result["status"] == "error"
        assert "400" in result["error"]


class TestSendSlackMessage:
    async def test_send_slack_success(self):
        patcher, _ = _mock_httpx(200)
        try:
            result = await send_slack_message("user-1", "https://hooks.slack.com/test", "Hello!")
        finally:
            patcher.stop()
        assert result["status"] == "sent"

    async def test_send_slack_failure(self):
        patcher, _ = _mock_httpx(403, text="Forbidden")
        try:
            result = await send_slack_message("user-1", "https://hooks.slack.com/test", "Hello!")
        finally:
            patcher.stop()
        assert result["status"] == "error"


class TestSendWebhook:
    async def test_send_webhook_success(self):
        patcher, _ = _mock_httpx(200)
        try:
            result = await send_webhook("user-1", "https://example.com/hook", {"e": "t"})
        finally:
            patcher.stop()
        assert result["status"] == "sent"
        assert result["response_status"] == 200

    async def test_send_webhook_with_custom_headers(self):
        patcher, _ = _mock_httpx(201)
        try:
            result = await send_webhook(
                "user-1",
                "https://example.com/hook",
                {"data": "test"},
                headers={"X-Custom": "value"},
            )
        finally:
            patcher.stop()
        assert result["status"] == "sent"
        assert result["response_status"] == 201

    async def test_send_webhook_error_response(self):
        patcher, _ = _mock_httpx(500)
        try:
            result = await send_webhook("user-1", "https://example.com/hook", {})
        finally:
            patcher.stop()
        assert result["status"] == "error"
        assert result["response_status"] == 500
