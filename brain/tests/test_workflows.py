"""Tests for the workflow engine and schema."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from brain.dependencies import verify_user
from brain.server import app
from brain.workflows.engine import _evaluate_condition, _resolve_next_step, execute_workflow
from brain.workflows.schema import (
    WorkflowCondition,
    WorkflowDefinition,
    WorkflowStep,
)


class TestWorkflowSchema:
    def test_valid_dag(self):
        wf = WorkflowDefinition(
            name="test",
            start="step1",
            steps=[
                WorkflowStep(id="step1", prompt="Hello {input}", next="step2"),
                WorkflowStep(id="step2", prompt="Summarize: {input}"),
            ],
        )
        assert wf.validate_dag() == []

    def test_invalid_start(self):
        wf = WorkflowDefinition(
            name="test",
            start="nonexistent",
            steps=[WorkflowStep(id="step1", prompt="Hello")],
        )
        errors = wf.validate_dag()
        assert any("nonexistent" in e for e in errors)

    def test_invalid_next_reference(self):
        wf = WorkflowDefinition(
            name="test",
            start="step1",
            steps=[WorkflowStep(id="step1", prompt="Hello", next="missing")],
        )
        errors = wf.validate_dag()
        assert any("missing" in e for e in errors)

    def test_invalid_condition_reference(self):
        wf = WorkflowDefinition(
            name="test",
            start="step1",
            steps=[
                WorkflowStep(
                    id="step1",
                    prompt="Hello",
                    conditions=[
                        WorkflowCondition(field="x", next_step="ghost"),
                    ],
                ),
            ],
        )
        errors = wf.validate_dag()
        assert any("ghost" in e for e in errors)

    def test_get_step(self):
        wf = WorkflowDefinition(
            name="test",
            start="s1",
            steps=[WorkflowStep(id="s1", prompt="Hello")],
        )
        assert wf.get_step("s1") is not None
        assert wf.get_step("nope") is None


class TestConditionEvaluation:
    def test_equals_json(self):
        cond = WorkflowCondition(field="status", operator="equals", value="ok", next_step="s2")
        assert _evaluate_condition(cond, '{"status": "ok"}') is True
        assert _evaluate_condition(cond, '{"status": "error"}') is False

    def test_contains(self):
        cond = WorkflowCondition(field="text", operator="contains", value="hello", next_step="s2")
        assert _evaluate_condition(cond, '{"text": "say hello world"}') is True
        assert _evaluate_condition(cond, '{"text": "goodbye"}') is False

    def test_exists(self):
        cond = WorkflowCondition(field="data", operator="exists", next_step="s2")
        assert _evaluate_condition(cond, '{"data": "value"}') is True
        assert _evaluate_condition(cond, '{"other": "value"}') is False

    def test_not_exists(self):
        cond = WorkflowCondition(field="error", operator="not_exists", next_step="s2")
        assert _evaluate_condition(cond, '{"data": "ok"}') is True

    def test_plain_text_input(self):
        cond = WorkflowCondition(field="text", operator="contains", value="hello", next_step="s2")
        assert _evaluate_condition(cond, "hello world") is True


class TestResolveNextStep:
    def test_condition_match(self):
        step = WorkflowStep(
            id="s1",
            prompt="test",
            next="default",
            conditions=[
                WorkflowCondition(
                    field="status", operator="equals", value="ok", next_step="success"
                ),
            ],
        )
        assert _resolve_next_step(step, '{"status": "ok"}') == "success"

    def test_default_next(self):
        step = WorkflowStep(id="s1", prompt="test", next="s2")
        assert _resolve_next_step(step, "anything") == "s2"

    def test_no_next(self):
        step = WorkflowStep(id="s1", prompt="test")
        assert _resolve_next_step(step, "anything") is None


class TestExecuteWorkflow:
    async def test_simple_workflow(self):
        wf = WorkflowDefinition(
            name="test",
            start="s1",
            steps=[
                WorkflowStep(id="s1", prompt="Process: {input}", next="s2"),
                WorkflowStep(id="s2", prompt="Summarize: {input}"),
            ],
        )

        mock_response = MagicMock()
        mock_response.content = "Processed output"
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("brain.workflows.engine.get_llm", return_value=mock_llm):
            result = await execute_workflow(wf, "test input")

        assert result.status == "completed"
        assert len(result.steps_executed) == 2

    async def test_workflow_invalid_dag(self):
        wf = WorkflowDefinition(
            name="bad",
            start="nonexistent",
            steps=[WorkflowStep(id="s1", prompt="Hello")],
        )
        result = await execute_workflow(wf, "input")
        assert result.status == "error"
        assert "Invalid workflow" in result.error

    async def test_workflow_max_steps(self):
        wf = WorkflowDefinition(
            name="loop",
            start="s1",
            max_steps=2,
            steps=[
                WorkflowStep(id="s1", prompt="{input}", next="s2"),
                WorkflowStep(id="s2", prompt="{input}", next="s1"),
            ],
        )

        mock_response = MagicMock()
        mock_response.content = "output"
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("brain.workflows.engine.get_llm", return_value=mock_llm):
            result = await execute_workflow(wf, "input")

        assert result.status == "max_steps_exceeded"

    async def test_workflow_with_conditions(self):
        wf = WorkflowDefinition(
            name="branching",
            start="check",
            steps=[
                WorkflowStep(
                    id="check",
                    prompt="Analyze: {input}",
                    conditions=[
                        WorkflowCondition(
                            field="status",
                            operator="equals",
                            value="ok",
                            next_step="success",
                        ),
                    ],
                    next="fallback",
                ),
                WorkflowStep(id="success", prompt="Handle success: {input}"),
                WorkflowStep(id="fallback", prompt="Handle fallback: {input}"),
            ],
        )

        mock_response = MagicMock()
        mock_response.content = '{"status": "ok"}'
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("brain.workflows.engine.get_llm", return_value=mock_llm):
            result = await execute_workflow(wf, "input")

        assert result.status == "completed"
        assert result.steps_executed[1]["step_id"] == "success"


class TestWorkflowEndpoints:
    @pytest.fixture
    def client(self):
        app.dependency_overrides[verify_user] = lambda: "user-1"
        try:
            yield TestClient(app, raise_server_exceptions=False)
        finally:
            app.dependency_overrides.clear()

    def test_validate_valid_workflow(self, client):
        resp = client.post(
            "/api/workflows/validate",
            json={
                "name": "test",
                "start": "s1",
                "steps": [{"id": "s1", "prompt": "Hello"}],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["errors"] == []

    def test_validate_invalid_workflow(self, client):
        resp = client.post(
            "/api/workflows/validate",
            json={
                "name": "test",
                "start": "missing",
                "steps": [{"id": "s1", "prompt": "Hello"}],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0
