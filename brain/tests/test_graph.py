"""Tests for the LangGraph agent graph logic."""

from langchain_core.messages import AIMessage

from brain.graph import _USER_SCOPED_TOOLS, should_continue


def test_should_continue_returns_execute_tools_when_tool_calls():
    msg = AIMessage(content="")
    msg.tool_calls = [{"id": "1", "name": "scrape_website", "args": {}}]
    state = {"messages": [msg]}  # type: ignore[typeddict-item]
    assert should_continue(state) == "execute_tools"


def test_should_continue_returns_end_when_no_tool_calls():
    msg = AIMessage(content="Done.")
    state = {"messages": [msg]}  # type: ignore[typeddict-item]
    assert should_continue(state) == "__end__"


def test_user_scoped_tools_contains_expected():
    assert "check_database_freshness" in _USER_SCOPED_TOOLS
    assert "save_metadata" in _USER_SCOPED_TOOLS
    assert "scrape_website" not in _USER_SCOPED_TOOLS
