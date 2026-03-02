"""Tests for per-user rate limiting."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from brain.rate_limit import _request_log, check_rate_limit


@pytest.fixture(autouse=True)
def clear_log():
    _request_log.clear()
    yield
    _request_log.clear()


def test_allows_requests_under_limit():
    for _ in range(5):
        check_rate_limit("user-1")


def test_blocks_requests_over_limit():
    with patch("brain.rate_limit.RATE_LIMIT_RPM", 3):
        check_rate_limit("user-1")
        check_rate_limit("user-1")
        check_rate_limit("user-1")
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit("user-1")
        assert exc_info.value.status_code == 429


def test_separate_users_have_separate_limits():
    with patch("brain.rate_limit.RATE_LIMIT_RPM", 2):
        check_rate_limit("user-a")
        check_rate_limit("user-a")
        # user-b should still be allowed
        check_rate_limit("user-b")
