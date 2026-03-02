"""Tests for run tracking tools."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from hands.tools.run_tools import get_run, list_runs, save_run


async def test_list_runs_returns_paginated():
    fake_rows = [
        {
            "id": "run-1",
            "agent": "chat",
            "status": "completed",
            "input_params": {"message": "hello"},
            "created_at": MagicMock(isoformat=lambda: "2025-01-01T00:00:00"),
        }
    ]

    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)
    mock_conn.fetch = AsyncMock(return_value=fake_rows)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=mock_conn)

    with patch("hands.tools.run_tools.get_pool", AsyncMock(return_value=mock_pool)):
        result = await list_runs("user-1", limit=10, offset=0)

    assert result["total"] == 1
    assert len(result["runs"]) == 1
    assert result["runs"][0]["agent"] == "chat"


async def test_get_run_returns_full_data():
    fake_row = {
        "id": "run-1",
        "agent": "chat",
        "status": "completed",
        "input_params": {"message": "hello"},
        "result": {"answer": "hi"},
        "messages": json.dumps([{"role": "user", "content": "hello"}]),
        "created_at": MagicMock(isoformat=lambda: "2025-01-01T00:00:00"),
    }

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=fake_row)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=mock_conn)

    with patch("hands.tools.run_tools.get_pool", AsyncMock(return_value=mock_pool)):
        result = await get_run("run-1", "user-1")

    assert result["id"] == "run-1"
    assert len(result["messages"]) == 1


async def test_get_run_returns_empty_when_not_found():
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=mock_conn)

    with patch("hands.tools.run_tools.get_pool", AsyncMock(return_value=mock_pool)):
        result = await get_run("nonexistent", "user-1")

    assert result == {}


async def test_save_run_persists():
    fake_row = {
        "id": "run-new",
        "created_at": MagicMock(isoformat=lambda: "2025-01-01T00:00:00"),
    }

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=fake_row)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=mock_conn)

    with patch("hands.tools.run_tools.get_pool", AsyncMock(return_value=mock_pool)):
        result = await save_run("user-1", "chat", {"message": "test"})

    assert result["id"] == "run-new"
