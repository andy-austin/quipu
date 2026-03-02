"""Per-user rate limiting for Brain endpoints."""

import os
import time

from fastapi import HTTPException, status

RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "30"))

# In-memory store: user_id -> list of request timestamps
_request_log: dict[str, list[float]] = {}


def check_rate_limit(user_id: str) -> None:
    """Raise 429 if user exceeds RATE_LIMIT_RPM requests per minute."""
    now = time.monotonic()
    window = 60.0

    timestamps = _request_log.get(user_id, [])
    # Prune old entries
    timestamps = [t for t in timestamps if now - t < window]
    if len(timestamps) >= RATE_LIMIT_RPM:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"},
        )
    timestamps.append(now)
    _request_log[user_id] = timestamps
