import json
import os
from datetime import UTC, datetime, timedelta

import asyncpg

from hands.logging import log

DB_URL = os.environ.get("SUPABASE_DB_URL", "")
FRESHNESS_HOURS = int(os.environ.get("FRESHNESS_HOURS", "24"))
DB_POOL_MIN = int(os.environ.get("DB_POOL_MIN", "2"))
DB_POOL_MAX = int(os.environ.get("DB_POOL_MAX", "10"))

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DB_URL, min_size=DB_POOL_MIN, max_size=DB_POOL_MAX)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def check_database_freshness(url: str) -> dict:
    """Check whether scraped data for a URL already exists and is fresh.

    Args:
        url: The target URL to look up in the database.

    Returns:
        A dict with keys ``fresh`` (bool) and ``data`` (the cached record or None).
    """
    log.info("checking_freshness", url=url)
    pool = await get_pool()
    async with pool.acquire() as conn:
        cutoff = datetime.now(UTC) - timedelta(hours=FRESHNESS_HOURS)
        row = await conn.fetchrow(
            "SELECT * FROM scraped_metadata WHERE url = $1 AND scraped_at > $2",
            url,
            cutoff,
        )
        if row:
            log.info("fresh_data_found", url=url)
            return {"fresh": True, "data": dict(row)}
        log.info("no_fresh_data", url=url)
        return {"fresh": False, "data": None}


async def save_metadata(url: str, metadata: dict) -> dict:
    """Persist scraped metadata for a URL.

    Args:
        url: The source URL.
        metadata: Arbitrary JSON-serialisable metadata to store.

    Returns:
        The saved record id and timestamp.
    """
    log.info("saving_metadata", url=url)
    # Defensive truncation for LLM safety
    if "text" in metadata and isinstance(metadata["text"], str):
        metadata["text"] = metadata["text"][:1000]

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO scraped_metadata (url, metadata, scraped_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (url) DO UPDATE
                SET metadata = EXCLUDED.metadata, scraped_at = NOW()
            RETURNING id, scraped_at
            """,
            url,
            json.dumps(metadata),
        )
        log.info("metadata_saved", url=url)
        return {"id": str(row["id"]), "scraped_at": row["scraped_at"].isoformat()}
