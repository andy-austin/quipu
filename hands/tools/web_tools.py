import asyncio

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from hands.logging import log

_MIN_TEXT_LENGTH = 200


async def _scrape_with_httpx(url: str) -> dict:
    """Fast, lightweight scrape via HTTP + BeautifulSoup."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(url, headers={"User-Agent": "Quipu/1.0"})
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    text = soup.get_text(separator=" ", strip=True)
    links = [a["href"] for a in soup.find_all("a", href=True)]

    return {"title": title, "text": text[:1000], "links": links[:20]}


async def _scrape_with_playwright(url: str) -> dict:
    """Full browser rendering for JS-heavy pages."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
        )
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_timeout(3000)  # let JS render
            title = await page.title()
            text = await page.inner_text("body")
            links = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            return {"title": title, "text": text[:1000], "links": links[:20]}
        finally:
            await browser.close()


async def scrape_website(url: str) -> dict:
    """Scrape a website, trying lightweight httpx first with Playwright fallback.

    Args:
        url: The fully-qualified URL to scrape.

    Returns:
        A dict with ``title``, ``text``, and ``links`` extracted from the page.
    """
    log.info("scrape_start", url=url)

    try:
        result = await _scrape_with_httpx(url)
        if len(result["text"]) >= _MIN_TEXT_LENGTH:
            log.info("scrape_success", url=url, method="httpx")
            return result
        log.info("scrape_thin_content", url=url, chars=len(result["text"]))
    except Exception as e:
        log.warning("scrape_httpx_failed", url=url, error=str(e))

    try:
        result = await asyncio.wait_for(_scrape_with_playwright(url), timeout=60)
        log.info("scrape_success", url=url, method="playwright")
        return result
    except TimeoutError:
        log.error("scrape_timeout", url=url)
        raise TimeoutError(f"Scraping timed out for {url}")
