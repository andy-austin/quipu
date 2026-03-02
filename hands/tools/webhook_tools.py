"""Tools for managing webhook registrations."""

import secrets

from hands.logging import log
from hands.tools.db_tools import get_pool


async def create_webhook(
    user_id: str,
    name: str,
    agent: str = "chat",
    system_prompt: str | None = None,
) -> dict:
    """Register a new webhook trigger for a user.

    Args:
        user_id: The webhook owner.
        name: Human-readable name for this webhook.
        agent: Agent type to run when triggered (default: chat).
        system_prompt: Optional system prompt override for the agent.

    Returns:
        Dict with webhook id and secret (shown once).
    """
    secret = secrets.token_urlsafe(32)
    log.info("create_webhook", user_id=user_id, name=name, agent=agent)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO webhooks (user_id, name, secret, agent, system_prompt) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING id",
            user_id,
            name,
            secret,
            agent,
            system_prompt,
        )
    webhook_id = str(row["id"])
    log.info("webhook_created", webhook_id=webhook_id)
    return {"id": webhook_id, "secret": secret, "name": name, "agent": agent}


async def list_webhooks(user_id: str) -> dict:
    """List all webhooks for a user.

    Args:
        user_id: The webhook owner.

    Returns:
        Dict with list of webhook summaries (no secrets).
    """
    log.info("list_webhooks", user_id=user_id)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, agent, active, created_at FROM webhooks "
            "WHERE user_id = $1 ORDER BY created_at DESC",
            user_id,
        )
    return {
        "webhooks": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "agent": r["agent"],
                "active": r["active"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    }


async def get_webhook(webhook_id: str) -> dict | None:
    """Get a webhook by ID (internal use — includes secret).

    Args:
        webhook_id: The webhook UUID.

    Returns:
        Dict with webhook details, or None if not found.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, user_id, name, secret, agent, system_prompt, active "
            "FROM webhooks WHERE id = $1",
            webhook_id,
        )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "user_id": row["user_id"],
        "name": row["name"],
        "secret": row["secret"],
        "agent": row["agent"],
        "system_prompt": row["system_prompt"],
        "active": row["active"],
    }


async def delete_webhook(user_id: str, webhook_id: str) -> dict:
    """Delete a webhook.

    Args:
        user_id: The webhook owner.
        webhook_id: The webhook UUID.

    Returns:
        Dict with deleted status.
    """
    log.info("delete_webhook", user_id=user_id, webhook_id=webhook_id)
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM webhooks WHERE id = $1 AND user_id = $2",
            webhook_id,
            user_id,
        )
    deleted = "DELETE 1" in result
    return {"webhook_id": webhook_id, "deleted": deleted}
