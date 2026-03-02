"""Tools for managing user-provided LLM API keys."""

import os

from cryptography.fernet import Fernet

from hands.logging import log
from hands.tools.db_tools import get_pool

# Encryption key from environment — generate with Fernet.generate_key()
_ENCRYPTION_KEY = os.environ.get("KEY_ENCRYPTION_KEY", "")
_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if not _ENCRYPTION_KEY:
            raise ValueError("KEY_ENCRYPTION_KEY environment variable is required")
        _fernet = Fernet(_ENCRYPTION_KEY.encode())
    return _fernet


def encrypt_key(api_key: str) -> str:
    """Encrypt an API key for storage."""
    return _get_fernet().encrypt(api_key.encode()).decode()


def decrypt_key(encrypted: str) -> str:
    """Decrypt a stored API key."""
    return _get_fernet().decrypt(encrypted.encode()).decode()


async def store_api_key(user_id: str, provider: str, api_key: str) -> dict:
    """Store or update a user's API key for a provider.

    Args:
        user_id: The key owner.
        provider: LLM provider name (e.g. 'google', 'groq').
        api_key: The raw API key to encrypt and store.

    Returns:
        Confirmation with provider name.
    """
    log.info("store_api_key", user_id=user_id, provider=provider)
    encrypted = encrypt_key(api_key)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO user_api_keys (user_id, provider, encrypted_key, updated_at) "
            "VALUES ($1, $2, $3, NOW()) "
            "ON CONFLICT (user_id, provider) DO UPDATE "
            "SET encrypted_key = EXCLUDED.encrypted_key, updated_at = NOW()",
            user_id,
            provider,
            encrypted,
        )
    log.info("api_key_stored", user_id=user_id, provider=provider)
    return {"provider": provider, "status": "stored"}


async def get_api_key(user_id: str, provider: str) -> dict:
    """Retrieve a user's decrypted API key for a provider.

    Args:
        user_id: The key owner.
        provider: LLM provider name.

    Returns:
        Dict with ``provider`` and ``api_key`` (decrypted), or empty if not found.
    """
    log.info("get_api_key", user_id=user_id, provider=provider)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT encrypted_key FROM user_api_keys WHERE user_id = $1 AND provider = $2",
            user_id,
            provider,
        )
    if not row:
        return {"provider": provider, "api_key": None}
    return {"provider": provider, "api_key": decrypt_key(row["encrypted_key"])}


async def delete_api_key(user_id: str, provider: str) -> dict:
    """Delete a user's API key for a provider.

    Args:
        user_id: The key owner.
        provider: LLM provider name.

    Returns:
        Confirmation with deleted status.
    """
    log.info("delete_api_key", user_id=user_id, provider=provider)
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM user_api_keys WHERE user_id = $1 AND provider = $2",
            user_id,
            provider,
        )
    deleted = "DELETE 1" in result
    return {"provider": provider, "deleted": deleted}


async def list_api_keys(user_id: str) -> dict:
    """List all providers for which the user has stored keys.

    Args:
        user_id: The key owner.

    Returns:
        Dict with ``providers`` list (names only, no keys).
    """
    log.info("list_api_keys", user_id=user_id)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT provider, updated_at FROM user_api_keys WHERE user_id = $1",
            user_id,
        )
    return {
        "providers": [
            {"provider": r["provider"], "updated_at": r["updated_at"].isoformat()} for r in rows
        ]
    }
