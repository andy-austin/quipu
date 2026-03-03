"""Workflow execution engine — runs a DAG of agent steps."""

import json

from brain.agents.registry import get_agent
from brain.logging import log
from brain.models import get_llm
from brain.workflows.schema import WorkflowCondition, WorkflowDefinition, WorkflowStep


class WorkflowResult:
    """Result of a workflow execution."""

    def __init__(self) -> None:
        self.steps_executed: list[dict] = []
        self.final_output: str = ""
        self.status: str = "pending"
        self.error: str | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "steps_executed": self.steps_executed,
            "final_output": self.final_output,
            "error": self.error,
        }


def _evaluate_condition(condition: WorkflowCondition, output: str) -> bool:
    """Evaluate a condition against step output."""
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        data = output

    # Get the field value
    if isinstance(data, dict):
        value = data.get(condition.field)
    else:
        value = str(data)

    if condition.operator == "exists":
        return value is not None
    if condition.operator == "not_exists":
        return value is None
    if condition.operator == "equals":
        return str(value) == str(condition.value)
    if condition.operator == "contains":
        return condition.value is not None and condition.value in str(value)
    return False


def _resolve_next_step(step: WorkflowStep, output: str) -> str | None:
    """Determine the next step based on conditions or default."""
    for condition in step.conditions:
        if _evaluate_condition(condition, output):
            log.info(
                "workflow_condition_matched",
                step=step.id,
                field=condition.field,
                next=condition.next_step,
            )
            return condition.next_step
    return step.next


async def execute_workflow(
    workflow: WorkflowDefinition,
    initial_input: str,
    model: str | None = None,
    user_id: str | None = None,
) -> WorkflowResult:
    """Execute a workflow DAG from start to completion.

    Args:
        workflow: The workflow definition.
        initial_input: Initial input text for the first step.
        model: LLM model to use (default from config).
        user_id: User context for agent runs.

    Returns:
        WorkflowResult with execution history and final output.
    """
    result = WorkflowResult()
    result.status = "running"

    errors = workflow.validate_dag()
    if errors:
        result.status = "error"
        result.error = f"Invalid workflow: {'; '.join(errors)}"
        return result

    current_step_id: str | None = workflow.start
    current_input = initial_input
    steps_run = 0

    log.info("workflow_start", name=workflow.name, start=workflow.start)

    while current_step_id and steps_run < workflow.max_steps:
        step = workflow.get_step(current_step_id)
        if step is None:
            result.status = "error"
            result.error = f"Step '{current_step_id}' not found"
            return result

        steps_run += 1
        log.info("workflow_step_start", step=step.id, agent=step.agent, iteration=steps_run)

        # Build the prompt with input substitution
        prompt = step.prompt.replace("{input}", current_input)

        # Resolve system prompt from step or agent definition
        system_prompt = step.system_prompt
        if not system_prompt:
            agent_def = get_agent(step.agent)
            if agent_def and agent_def.system_prompt:
                system_prompt = agent_def.system_prompt

        # Run the LLM
        try:
            llm = get_llm(model)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = await llm.ainvoke(messages)
            output = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            log.error("workflow_step_error", step=step.id, error=str(e))
            result.status = "error"
            result.error = f"Step '{step.id}' failed: {e}"
            result.steps_executed.append(
                {
                    "step_id": step.id,
                    "agent": step.agent,
                    "input": prompt[:500],
                    "output": None,
                    "error": str(e),
                }
            )
            return result

        result.steps_executed.append(
            {
                "step_id": step.id,
                "agent": step.agent,
                "input": prompt[:500],
                "output": str(output)[:2000],
            }
        )
        log.info("workflow_step_complete", step=step.id)

        # Determine next step
        current_input = str(output)
        current_step_id = _resolve_next_step(step, current_input)

    result.final_output = current_input
    if steps_run >= workflow.max_steps:
        result.status = "max_steps_exceeded"
        result.error = f"Workflow exceeded {workflow.max_steps} step limit"
    else:
        result.status = "completed"

    log.info("workflow_complete", name=workflow.name, steps=steps_run, status=result.status)
    return result
