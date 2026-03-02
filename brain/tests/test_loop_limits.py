"""Tests for LangGraph recursion limit configuration."""

from brain.graph import RECURSION_LIMIT


def test_default_recursion_limit():
    assert RECURSION_LIMIT == 25


def test_recursion_limit_from_env(monkeypatch):
    monkeypatch.setenv("LANGGRAPH_RECURSION_LIMIT", "10")
    # Re-import to pick up changed env
    import importlib

    import brain.graph as g

    importlib.reload(g)
    assert g.RECURSION_LIMIT == 10
    # Restore
    monkeypatch.delenv("LANGGRAPH_RECURSION_LIMIT")
    importlib.reload(g)
