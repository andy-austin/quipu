import os
import json
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
    print(f"Checking freshness for: {url}")
    conn = await _get_conn()
    try:
        cutoff = datetime.now(UTC) - timedelta(hours=FRESHNESS_HOURS)
        row = await conn.fetchrow(
            "SELECT * FROM scraped_metadata WHERE url = $1 AND scraped_at > $2",
            url,
            cutoff,
        )
        if row:
            print(f"Found fresh data for: {url}")
            return {"fresh": True, "data": dict(row)}
        print(f"No fresh data found for: {url}")
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
    print(f"Saving metadata for: {url}")
    # Defensive truncation for LLM safety
    if "text" in metadata and isinstance(metadata["text"], str):
        metadata["text"] = metadata["text"][:1000]

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
            json.dumps(metadata),
        )
        print(f"Successfully saved metadata for: {url}")
        return {"id": str(row["id"]), "scraped_at": row["scraped_at"].isoformat()}
    except Exception as e:
        print(f"Error saving metadata for {url}: {e}")
        raise
    finally:
        await conn.close()
