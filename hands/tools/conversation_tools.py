"""Conversation persistence tools for multi-turn message history."""

import json

from hands.logging import log
from hands.tools.db_tools import get_pool


async def load_conversation(conversation_id: str, user_id: str) -> dict:
    """Load message history for a conversation.

    Args:
        conversation_id: The conversation UUID.
        user_id: Owner of the conversation.

    Returns:
        A dict with ``conversation_id`` and ``messages`` (list of message dicts).
    """
    log.info("load_conversation", conversation_id=conversation_id, user_id=user_id)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT messages FROM conversations WHERE id = $1 AND user_id = $2",
            conversation_id,
            user_id,
        )
        if row:
            raw = row["messages"]
            messages = json.loads(raw) if isinstance(raw, str) else raw
            log.info("conversation_loaded", conversation_id=conversation_id, count=len(messages))
            return {"conversation_id": conversation_id, "messages": messages}
        log.info("conversation_not_found", conversation_id=conversation_id)
        return {"conversation_id": conversation_id, "messages": []}


async def save_conversation(conversation_id: str, user_id: str, messages: list[dict]) -> dict:
    """Save message history for a conversation (upsert).

    Args:
        conversation_id: The conversation UUID.
        user_id: Owner of the conversation.
        messages: List of message dicts to persist.

    Returns:
        A dict with ``conversation_id`` and ``updated_at``.
    """
    log.info("save_conversation", conversation_id=conversation_id, user_id=user_id)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO conversations (id, user_id, messages, updated_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (id) DO UPDATE
                SET messages = EXCLUDED.messages, updated_at = NOW()
            RETURNING id, updated_at
            """,
            conversation_id,
            user_id,
            json.dumps(messages),
        )
        log.info("conversation_saved", conversation_id=conversation_id)
        return {
            "conversation_id": str(row["id"]),
            "updated_at": row["updated_at"].isoformat(),
        }
