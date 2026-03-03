"""Workflow definition schema — DAG of agent steps."""

from pydantic import BaseModel, Field


class WorkflowCondition(BaseModel):
    """Conditional branch based on a step's output."""

    field: str = Field(..., description="JSON path in the step output to check")
    operator: str = Field(
        default="equals", description="Comparison operator: equals, contains, exists, not_exists"
    )
    value: str | None = Field(default=None, description="Value to compare against")
    next_step: str = Field(..., description="Step ID to jump to if condition matches")


class WorkflowStep(BaseModel):
    """A single step in a workflow DAG."""

    id: str = Field(..., description="Unique step identifier")
    agent: str = Field(default="chat", description="Agent type to run")
    prompt: str = Field(..., description="Prompt template — use {input} for previous output")
    system_prompt: str | None = Field(default=None, description="Optional system prompt override")
    next: str | None = Field(default=None, description="Default next step ID (None = end)")
    conditions: list[WorkflowCondition] = Field(
        default_factory=list, description="Conditional branches evaluated in order"
    )


class WorkflowDefinition(BaseModel):
    """A complete workflow DAG definition."""

    name: str = Field(..., description="Workflow name")
    description: str = Field(default="", description="What this workflow does")
    start: str = Field(..., description="ID of the first step")
    steps: list[WorkflowStep] = Field(..., description="All steps in the workflow")
    max_steps: int = Field(default=20, description="Maximum steps to prevent infinite loops")

    def get_step(self, step_id: str) -> WorkflowStep | None:
        """Look up a step by ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def validate_dag(self) -> list[str]:
        """Validate the DAG structure. Returns list of errors (empty = valid)."""
        errors = []
        step_ids = {s.id for s in self.steps}

        if self.start not in step_ids:
            errors.append(f"Start step '{self.start}' not found")

        for step in self.steps:
            if step.next and step.next not in step_ids:
                errors.append(f"Step '{step.id}' references unknown next '{step.next}'")
            for cond in step.conditions:
                if cond.next_step not in step_ids:
                    errors.append(
                        f"Step '{step.id}' condition references unknown '{cond.next_step}'"
                    )

        return errors
