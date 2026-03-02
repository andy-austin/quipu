"""Predefined Pydantic schemas for structured data extraction."""

from pydantic import BaseModel, Field


class ContactInfo(BaseModel):
    """Contact information extracted from a page."""

    name: str | None = Field(default=None, description="Person or organization name")
    email: str | None = Field(default=None, description="Email address")
    phone: str | None = Field(default=None, description="Phone number")
    address: str | None = Field(default=None, description="Physical address")
    website: str | None = Field(default=None, description="Website URL")


class ProductInfo(BaseModel):
    """Product information extracted from a page."""

    name: str = Field(description="Product name")
    price: str | None = Field(default=None, description="Price as displayed")
    description: str | None = Field(default=None, description="Product description")
    currency: str | None = Field(default=None, description="Currency code")
    availability: str | None = Field(default=None, description="Availability status")


class ArticleInfo(BaseModel):
    """Article metadata extracted from a page."""

    title: str = Field(description="Article title")
    author: str | None = Field(default=None, description="Author name")
    published_date: str | None = Field(default=None, description="Publication date")
    summary: str | None = Field(default=None, description="Brief summary")
    tags: list[str] = Field(default_factory=list, description="Tags or categories")


class PageMetadata(BaseModel):
    """General page metadata."""

    title: str = Field(description="Page title")
    description: str | None = Field(default=None, description="Page description")
    language: str | None = Field(default=None, description="Content language")
    links: list[str] = Field(default_factory=list, description="Important links")


EXTRACTION_SCHEMAS: dict[str, type[BaseModel]] = {
    "contact": ContactInfo,
    "product": ProductInfo,
    "article": ArticleInfo,
    "page": PageMetadata,
}
