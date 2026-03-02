"""Tests for the structured data extraction agent."""

import json
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage

from brain.extraction_graph import build_extraction_graph, should_continue
from brain.extraction_schemas import EXTRACTION_SCHEMAS, ArticleInfo, ContactInfo, ProductInfo
from brain.server import app


def test_should_continue_returns_tools_when_tool_calls():
    msg = AIMessage(content="")
    msg.tool_calls = [{"id": "1", "name": "scrape_website", "args": {}}]
    state = {"messages": [msg]}  # type: ignore[typeddict-item]
    assert should_continue(state) == "execute_tools"


def test_should_continue_returns_validate_when_no_tools():
    msg = AIMessage(content='{"title": "Test"}')
    state = {"messages": [msg]}  # type: ignore[typeddict-item]
    assert should_continue(state) == "validate"


def test_extraction_schemas_registered():
    assert "contact" in EXTRACTION_SCHEMAS
    assert "product" in EXTRACTION_SCHEMAS
    assert "article" in EXTRACTION_SCHEMAS
    assert "page" in EXTRACTION_SCHEMAS


def test_contact_schema_validates():
    data = ContactInfo(name="John", email="john@example.com")
    assert data.name == "John"
    assert data.email == "john@example.com"


def test_product_schema_validates():
    data = ProductInfo(name="Widget", price="$9.99")
    assert data.name == "Widget"


def test_article_schema_validates():
    data = ArticleInfo(title="Test Article", tags=["tech"])
    assert data.title == "Test Article"
    assert len(data.tags) == 1


def test_build_extraction_graph_compiles():
    graph = build_extraction_graph()
    assert graph is not None


async def test_extract_endpoint_returns_sse():
    """Test the /api/extract/stream endpoint."""
    fake_ai_msg = AIMessage(content='{"title": "Test Page"}')

    async def fake_astream(initial_state, config=None):
        yield {"extract": {"messages": [fake_ai_msg]}}
        yield {"validate": {"extracted_data": '{"title": "Test Page"}'}}

    with patch("brain.server.extraction_graph") as mock_graph:
        mock_graph.astream = fake_astream

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/extract/stream",
                params={"url": "https://example.com", "schema_name": "page"},
            )
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]

            events = []
            for line in resp.text.strip().split("\n"):
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

            types = [e["type"] for e in events]
            assert "done" in types
