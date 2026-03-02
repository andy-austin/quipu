"""Tests for JWT authentication dependency."""

import pytest
from fastapi import HTTPException
from jose import jwt

from brain.dependencies import ALGORITHM, verify_user


@pytest.fixture
def valid_token():
    return jwt.encode(
        {"sub": "user-123", "aud": "authenticated"},
        "test-secret",
        algorithm=ALGORITHM,
    )


@pytest.fixture
def expired_token():
    return jwt.encode(
        {"sub": "user-123", "aud": "wrong-audience"},
        "test-secret",
        algorithm=ALGORITHM,
    )


class FakeCredentials:
    def __init__(self, token: str):
        self.credentials = token


async def test_valid_token_returns_user_id(valid_token):
    creds = FakeCredentials(valid_token)
    user_id = await verify_user(creds)
    assert user_id == "user-123"


async def test_invalid_token_raises_401():
    creds = FakeCredentials("invalid-jwt-token")
    with pytest.raises(HTTPException) as exc_info:
        await verify_user(creds)
    assert exc_info.value.status_code == 401


async def test_wrong_audience_raises_401(expired_token):
    creds = FakeCredentials(expired_token)
    with pytest.raises(HTTPException) as exc_info:
        await verify_user(creds)
    assert exc_info.value.status_code == 401
