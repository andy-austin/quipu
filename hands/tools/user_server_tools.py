"""Tools for managing user-registered MCP server endpoints."""

from hands.logging import log
from hands.tools.db_tools import get_pool


async def register_user_server(
    user_id: str,
    name: str,
    url: str,
    auth_token: str | None = None,
) -> dict:
    """Register a user's own MCP server endpoint.

    Args:
        user_id: The server owner.
        name: Human-readable name for this server.
        url: MCP server SSE URL.
        auth_token: Optional auth token for the server.

    Returns:
        Dict with server id and metadata.
    """
    log.info("register_user_server", user_id=user_id, name=name, url=url)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO user_mcp_servers (user_id, name, url, auth_token) "
            "VALUES ($1, $2, $3, $4) "
            "ON CONFLICT (user_id, name) DO UPDATE "
            "SET url = EXCLUDED.url, auth_token = EXCLUDED.auth_token "
            "RETURNING id, created_at",
            user_id,
            name,
            url,
            auth_token,
        )
    return {
        "id": str(row["id"]),
        "name": name,
        "url": url,
        "created_at": row["created_at"].isoformat(),
    }


async def list_user_servers(user_id: str) -> dict:
    """List a user's registered MCP servers.

    Args:
        user_id: The server owner.

    Returns:
        Dict with list of server summaries (no auth tokens).
    """
    log.info("list_user_servers", user_id=user_id)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, url, active, created_at FROM user_mcp_servers "
            "WHERE user_id = $1 ORDER BY created_at DESC",
            user_id,
        )
    return {
        "servers": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "url": r["url"],
                "active": r["active"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    }


async def delete_user_server(user_id: str, server_id: str) -> dict:
    """Delete a user's registered MCP server.

    Args:
        user_id: The server owner.
        server_id: The server UUID.

    Returns:
        Dict with deleted status.
    """
    log.info("delete_user_server", user_id=user_id, server_id=server_id)
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM user_mcp_servers WHERE id = $1 AND user_id = $2",
            server_id,
            user_id,
        )
    deleted = "DELETE 1" in result
    return {"server_id": server_id, "deleted": deleted}
