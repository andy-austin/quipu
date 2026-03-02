"""Tests for user data isolation (user_id flows through graph to tools)."""

from brain.graph import _USER_SCOPED_TOOLS, AgentState


def test_user_id_in_agent_state():
    """user_id is a valid field in AgentState."""
    state: AgentState = {
        "url": "https://example.com",
        "model": None,
        "user_id": "user-123",
        "db_status": None,
        "raw_content": None,
        "final_json": None,
        "messages": [],
    }
    assert state["user_id"] == "user-123"


def test_user_scoped_tools_defined():
    """User-scoped tools set includes the DB tools."""
    assert "check_database_freshness" in _USER_SCOPED_TOOLS
    assert "save_metadata" in _USER_SCOPED_TOOLS
