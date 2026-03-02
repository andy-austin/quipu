"""Tests for CORS middleware configuration."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app_with_cors():
    """Create app with CORS_ORIGINS set."""
    with patch.dict("os.environ", {"CORS_ORIGINS": "https://app.example.com,https://other.com"}):
        # Re-import to pick up the env var
        import importlib

        import brain.server as srv

        importlib.reload(srv)
        yield srv.app


@pytest.fixture
def app_no_cors():
    """Create app with no CORS_ORIGINS (empty)."""
    with patch.dict("os.environ", {"CORS_ORIGINS": ""}, clear=False):
        import importlib

        import brain.server as srv

        importlib.reload(srv)
        yield srv.app


async def test_cors_allows_configured_origin(app_with_cors):
    transport = ASGITransport(app=app_with_cors)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.options(
            "/health",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") == "https://app.example.com"


async def test_cors_blocks_unknown_origin(app_with_cors):
    transport = ASGITransport(app=app_with_cors)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.options(
            "/health",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in resp.headers


async def test_cors_empty_origins_blocks_all(app_no_cors):
    transport = ASGITransport(app=app_no_cors)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.options(
            "/health",
            headers={
                "Origin": "https://anything.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in resp.headers
