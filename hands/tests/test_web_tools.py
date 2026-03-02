"""Tests for the web scraping tools."""

from unittest.mock import AsyncMock, MagicMock, patch

from hands.tools.web_tools import _MIN_TEXT_LENGTH, _scrape_with_httpx, scrape_website


async def test_scrape_with_httpx_extracts_content():
    html = (
        "<html><head><title>Test Page</title></head>"
        "<body><p>Hello world</p>"
        '<a href="https://example.com">Link</a></body></html>'
    )
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("hands.tools.web_tools.httpx.AsyncClient", return_value=mock_client):
        result = await _scrape_with_httpx("https://example.com")

    assert result["title"] == "Test Page"
    assert "Hello world" in result["text"]
    assert "https://example.com" in result["links"]


async def test_scrape_website_uses_httpx_when_sufficient():
    long_text = "x" * (_MIN_TEXT_LENGTH + 1)
    httpx_result = {"title": "T", "text": long_text, "links": []}

    with patch("hands.tools.web_tools._scrape_with_httpx", AsyncMock(return_value=httpx_result)):
        result = await scrape_website("https://example.com")

    assert result["text"] == long_text


async def test_scrape_website_falls_back_to_playwright():
    thin_result = {"title": "T", "text": "short", "links": []}
    pw_result = {"title": "Full", "text": "rendered content", "links": []}

    with (
        patch("hands.tools.web_tools._scrape_with_httpx", AsyncMock(return_value=thin_result)),
        patch("hands.tools.web_tools._scrape_with_playwright", AsyncMock(return_value=pw_result)),
    ):
        result = await scrape_website("https://example.com")

    assert result["title"] == "Full"
