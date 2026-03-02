import asyncio

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

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
    print(f"Scraping website: {url}")

    try:
        result = await _scrape_with_httpx(url)
        if len(result["text"]) >= _MIN_TEXT_LENGTH:
            print(f"Successfully scraped (httpx): {url}")
            return result
        print(f"Thin content from httpx ({len(result['text'])} chars), falling back to Playwright")
    except Exception as e:
        print(f"httpx failed ({e}), falling back to Playwright")

    try:
        result = await asyncio.wait_for(_scrape_with_playwright(url), timeout=60)
        print(f"Successfully scraped (playwright): {url}")
        return result
    except TimeoutError:
        print(f"Playwright timed out for {url}")
        raise TimeoutError(f"Scraping timed out for {url} — site may require JavaScript rendering")
