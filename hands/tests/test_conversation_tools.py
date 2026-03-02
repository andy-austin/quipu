"""Tests for conversation persistence tools."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from hands.tools.conversation_tools import load_conversation, save_conversation


async def test_load_conversation_returns_messages_when_found():
    messages = [{"role": "user", "content": "Hello"}]
    fake_row = {"messages": json.dumps(messages)}

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=fake_row)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=mock_conn)

    with patch("hands.tools.conversation_tools.get_pool", AsyncMock(return_value=mock_pool)):
        result = await load_conversation("conv-1", "user-1")

    assert result["conversation_id"] == "conv-1"
    assert len(result["messages"]) == 1
    assert result["messages"][0]["content"] == "Hello"


async def test_load_conversation_returns_empty_when_not_found():
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=mock_conn)

    with patch("hands.tools.conversation_tools.get_pool", AsyncMock(return_value=mock_pool)):
        result = await load_conversation("conv-1", "user-1")

    assert result["messages"] == []


async def test_save_conversation_upserts():
    messages = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}]
    fake_row = {
        "id": "conv-1",
        "updated_at": MagicMock(isoformat=lambda: "2025-01-01T00:00:00"),
    }

    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=fake_row)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)

    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=mock_conn)

    with patch("hands.tools.conversation_tools.get_pool", AsyncMock(return_value=mock_pool)):
        result = await save_conversation("conv-1", "user-1", messages)

    assert result["conversation_id"] == "conv-1"
    # Verify the messages were serialized
    call_args = mock_conn.fetchrow.call_args
    stored = json.loads(call_args[0][3])
    assert len(stored) == 2
