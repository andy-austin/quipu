import os
from datetime import UTC, datetime, timedelta

import asyncpg

DB_URL = os.environ.get("SUPABASE_DB_URL", "")
FRESHNESS_HOURS = int(os.environ.get("FRESHNESS_HOURS", "24"))


async def _get_conn() -> asyncpg.Connection:
    return await asyncpg.connect(DB_URL)


async def check_database_freshness(url: str) -> dict:
    """Check whether scraped data for a URL already exists and is fresh.

    Args:
        url: The target URL to look up in the database.

    Returns:
        A dict with keys ``fresh`` (bool) and ``data`` (the cached record or None).
    """
    conn = await _get_conn()
    try:
        cutoff = datetime.now(UTC) - timedelta(hours=FRESHNESS_HOURS)
        row = await conn.fetchrow(
            "SELECT * FROM scraped_metadata WHERE url = $1 AND scraped_at > $2",
            url,
            cutoff,
        )
        if row:
            return {"fresh": True, "data": dict(row)}
        return {"fresh": False, "data": None}
    finally:
        await conn.close()


async def save_metadata(url: str, metadata: dict) -> dict:
    """Persist scraped metadata for a URL.

    Args:
        url: The source URL.
        metadata: Arbitrary JSON-serialisable metadata to store.

    Returns:
        The saved record id and timestamp.
    """
    conn = await _get_conn()
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO scraped_metadata (url, metadata, scraped_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (url) DO UPDATE
                SET metadata = EXCLUDED.metadata, scraped_at = NOW()
            RETURNING id, scraped_at
            """,
            url,
            metadata,
        )
        return {"id": str(row["id"]), "scraped_at": row["scraped_at"].isoformat()}
    finally:
        await conn.close()
