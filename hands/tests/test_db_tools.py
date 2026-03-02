"""Tests for the database tools."""

from unittest.mock import AsyncMock, MagicMock, patch

from hands.tools.db_tools import check_database_freshness, save_metadata


async def test_check_freshness_returns_fresh_when_found():
    fake_row = {"url": "https://example.com", "metadata": "{}", "scraped_at": "2025-01-01T00:00:00"}
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=fake_row)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=mock_conn)

    with patch("hands.tools.db_tools.get_pool", AsyncMock(return_value=mock_pool)):
        result = await check_database_freshness("https://example.com")

    assert result["fresh"] is True
    assert result["data"] is not None


async def test_check_freshness_returns_not_fresh_when_missing():
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=mock_conn)

    with patch("hands.tools.db_tools.get_pool", AsyncMock(return_value=mock_pool)):
        result = await check_database_freshness("https://example.com", user_id="user-1")

    assert result["fresh"] is False
    assert result["data"] is None


async def test_save_metadata_truncates_text():
    long_text = "x" * 2000
    fake_row = {"id": "abc-123", "scraped_at": MagicMock(isoformat=lambda: "2025-01-01T00:00:00")}

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=fake_row)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=mock_conn)

    with patch("hands.tools.db_tools.get_pool", AsyncMock(return_value=mock_pool)):
        result = await save_metadata("https://example.com", {"text": long_text}, user_id="u1")

    assert result["id"] == "abc-123"
    # Verify the text was truncated in the args passed to fetchrow
    # Args: (query, url, metadata_json, user_id)
    call_args = mock_conn.fetchrow.call_args
    import json

    stored_metadata = json.loads(call_args[0][2])
    assert len(stored_metadata["text"]) == 1000
