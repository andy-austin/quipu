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
