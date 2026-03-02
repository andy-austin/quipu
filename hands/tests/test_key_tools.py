"""Tests for hands.tools.key_tools — BYOK key management."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hands.tools import key_tools


@pytest.fixture(autouse=True)
def _reset_fernet():
    """Reset the module-level Fernet singleton between tests."""
    key_tools._fernet = None
    yield
    key_tools._fernet = None


@pytest.fixture
def fernet_key():
    """A valid Fernet key for testing."""
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


def _mock_pool(mock_conn):
    """Create a mock pool matching the pattern used in db_tools tests."""
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=False)
    mock_pool = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=mock_conn)
    return mock_pool


class TestEncryptDecrypt:
    def test_roundtrip(self, fernet_key):
        with patch.object(key_tools, "_ENCRYPTION_KEY", fernet_key):
            encrypted = key_tools.encrypt_key("my-secret-key")
            assert encrypted != "my-secret-key"
            assert key_tools.decrypt_key(encrypted) == "my-secret-key"

    def test_missing_encryption_key_raises(self):
        with patch.object(key_tools, "_ENCRYPTION_KEY", ""):
            with pytest.raises(ValueError, match="KEY_ENCRYPTION_KEY"):
                key_tools.encrypt_key("anything")


class TestStoreApiKey:
    async def test_store_api_key(self, fernet_key):
        mock_conn = AsyncMock()
        mock_pool = _mock_pool(mock_conn)

        with (
            patch.object(key_tools, "_ENCRYPTION_KEY", fernet_key),
            patch("hands.tools.key_tools.get_pool", AsyncMock(return_value=mock_pool)),
        ):
            result = await key_tools.store_api_key("user-1", "google", "goog-key-123")

        assert result == {"provider": "google", "status": "stored"}
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        assert "INSERT INTO user_api_keys" in call_args[0]
        assert call_args[1] == "user-1"
        assert call_args[2] == "google"
        assert call_args[3] != "goog-key-123"


class TestGetApiKey:
    async def test_get_existing_key(self, fernet_key):
        with patch.object(key_tools, "_ENCRYPTION_KEY", fernet_key):
            encrypted = key_tools.encrypt_key("my-api-key")

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"encrypted_key": encrypted})
        mock_pool = _mock_pool(mock_conn)

        with (
            patch.object(key_tools, "_ENCRYPTION_KEY", fernet_key),
            patch("hands.tools.key_tools.get_pool", AsyncMock(return_value=mock_pool)),
        ):
            result = await key_tools.get_api_key("user-1", "google")

        assert result == {"provider": "google", "api_key": "my-api-key"}

    async def test_get_missing_key(self, fernet_key):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool = _mock_pool(mock_conn)

        with (
            patch.object(key_tools, "_ENCRYPTION_KEY", fernet_key),
            patch("hands.tools.key_tools.get_pool", AsyncMock(return_value=mock_pool)),
        ):
            result = await key_tools.get_api_key("user-1", "openai")

        assert result == {"provider": "openai", "api_key": None}


class TestDeleteApiKey:
    async def test_delete_existing(self):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 1")
        mock_pool = _mock_pool(mock_conn)

        with patch("hands.tools.key_tools.get_pool", AsyncMock(return_value=mock_pool)):
            result = await key_tools.delete_api_key("user-1", "google")

        assert result == {"provider": "google", "deleted": True}

    async def test_delete_nonexistent(self):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 0")
        mock_pool = _mock_pool(mock_conn)

        with patch("hands.tools.key_tools.get_pool", AsyncMock(return_value=mock_pool)):
            result = await key_tools.delete_api_key("user-1", "google")

        assert result == {"provider": "google", "deleted": False}


class TestListApiKeys:
    async def test_list_keys(self):
        ts = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            return_value=[
                {"provider": "google", "updated_at": ts},
                {"provider": "groq", "updated_at": ts},
            ]
        )
        mock_pool = _mock_pool(mock_conn)

        with patch("hands.tools.key_tools.get_pool", AsyncMock(return_value=mock_pool)):
            result = await key_tools.list_api_keys("user-1")

        assert len(result["providers"]) == 2
        assert result["providers"][0]["provider"] == "google"
        assert result["providers"][1]["provider"] == "groq"

    async def test_list_empty(self):
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool = _mock_pool(mock_conn)

        with patch("hands.tools.key_tools.get_pool", AsyncMock(return_value=mock_pool)):
            result = await key_tools.list_api_keys("user-1")

        assert result == {"providers": []}
