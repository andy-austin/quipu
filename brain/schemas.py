"""Pydantic request/response schemas for Brain API."""

from pydantic import BaseModel, Field, HttpUrl

from brain.models import SUPPORTED_MODELS

_model_names = list(SUPPORTED_MODELS.keys())


class ScrapeRequest(BaseModel):
    """Query parameters for scraping endpoints."""

    url: HttpUrl = Field(..., description="Fully-qualified URL to scrape")
    model: str | None = Field(
        default=None,
        description=f"LLM model identifier. Supported: {_model_names}",
    )


class ChatRequest(BaseModel):
    """Query parameters for chat endpoints."""

    message: str = Field(..., description="User message to send to the agent")
    agent: str = Field(default="chat", description="Agent type: 'chat' or 'scrape'")
    model: str | None = Field(
        default=None,
        description=f"LLM model identifier. Supported: {_model_names}",
    )
    system_prompt: str | None = Field(
        default=None,
        description="Custom system prompt for the agent",
    )
    url: HttpUrl | None = Field(
        default=None,
        description="URL for scrape agent (required when agent=scrape)",
    )
    conversation_id: str | None = Field(
        default=None,
        description="Conversation ID for multi-turn persistence",
    )
