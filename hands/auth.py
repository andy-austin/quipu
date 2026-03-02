"""Token-based authentication middleware for user-hosted Hands instances."""

import os

from hands.logging import log

# Set HANDS_AUTH_TOKEN to require token auth on a self-hosted instance
_AUTH_TOKEN = os.environ.get("HANDS_AUTH_TOKEN", "")


def verify_token(token: str) -> bool:
    """Verify that the provided token matches the configured auth token.

    If HANDS_AUTH_TOKEN is not set, auth is disabled (open access).
    """
    if not _AUTH_TOKEN:
        return True
    valid = token == _AUTH_TOKEN
    if not valid:
        log.warning("auth_token_invalid")
    return valid
