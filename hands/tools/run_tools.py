"""Tools for tracking and querying past agent runs."""

import json

from hands.logging import log
from hands.tools.db_tools import get_pool


async def list_runs(user_id: str, limit: int = 20, offset: int = 0) -> dict:
    """List past agent runs for a user with pagination.

    Args:
        user_id: The user whose runs to list.
        limit: Maximum number of results (default 20, max 100).
        offset: Number of results to skip for pagination.

    Returns:
        A dict with ``runs`` (list) and ``total`` count.
    """
    limit = min(limit, 100)
    log.info("list_runs", user_id=user_id, limit=limit, offset=offset)
    pool = await get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM runs WHERE user_id = $1", user_id)
        rows = await conn.fetch(
            "SELECT id, agent, status, input_params, created_at FROM runs "
            "WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
            user_id,
            limit,
            offset,
        )
        runs = [
            {
                "id": str(r["id"]),
                "agent": r["agent"],
                "status": r["status"],
                "input_params": r["input_params"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
        log.info("runs_listed", user_id=user_id, count=len(runs))
        return {"runs": runs, "total": total}


async def get_run(run_id: str, user_id: str) -> dict:
    """Get a single run with full conversation and result data.

    Args:
        run_id: The run UUID.
        user_id: Owner of the run (for data isolation).

    Returns:
        The full run record or an empty dict if not found.
    """
    log.info("get_run", run_id=run_id, user_id=user_id)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT r.id, r.agent, r.status, r.input_params, r.result, r.created_at, "
            "c.messages FROM runs r LEFT JOIN conversations c ON r.conversation_id = c.id "
            "WHERE r.id = $1 AND r.user_id = $2",
            run_id,
            user_id,
        )
        if not row:
            log.info("run_not_found", run_id=run_id)
            return {}
        messages = row["messages"]
        if isinstance(messages, str):
            messages = json.loads(messages)
        return {
            "id": str(row["id"]),
            "agent": row["agent"],
            "status": row["status"],
            "input_params": row["input_params"],
            "result": row["result"],
            "messages": messages or [],
            "created_at": row["created_at"].isoformat(),
        }


async def save_run(
    user_id: str,
    agent: str,
    input_params: dict,
    result: dict | None = None,
    conversation_id: str | None = None,
) -> dict:
    """Save a completed agent run.

    Args:
        user_id: Owner of the run.
        agent: Agent type used.
        input_params: Input parameters for the run.
        result: Optional result data.
        conversation_id: Optional linked conversation.

    Returns:
        The saved run id and timestamp.
    """
    log.info("save_run", user_id=user_id, agent=agent)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO runs (user_id, agent, input_params, result, conversation_id) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING id, created_at",
            user_id,
            agent,
            json.dumps(input_params),
            json.dumps(result) if result else None,
            conversation_id,
        )
        log.info("run_saved", run_id=str(row["id"]))
        return {"id": str(row["id"]), "created_at": row["created_at"].isoformat()}
