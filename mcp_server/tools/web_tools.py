import os

from playwright.async_api import async_playwright

BROWSERLESS_URL = os.environ.get(
    "BROWSERLESS_URL", "wss://chrome.browserless.io"
)
BROWSERLESS_API_KEY = os.environ.get("BROWSERLESS_API_KEY", "")


async def scrape_website(url: str) -> dict:
    """Scrape a target website via Browserless.io (Playwright over WebSocket).

    Args:
        url: The fully-qualified URL to scrape.

    Returns:
        A dict with ``title``, ``text``, and ``links`` extracted from the page.
    """
    ws_endpoint = f"{BROWSERLESS_URL}?token={BROWSERLESS_API_KEY}"

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(ws_endpoint)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=30_000)
            title = await page.title()
            text = await page.inner_text("body")
            links = await page.eval_on_selector_all(
                "a[href]", "els => els.map(e => e.href)"
            )
            return {"title": title, "text": text[:5000], "links": links[:50]}
        finally:
            await browser.close()
