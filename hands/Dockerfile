FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN uv pip install --system --no-cache \
    "fastmcp>=2.3" "asyncpg>=0.30" "beautifulsoup4>=4.12" "playwright>=1.50" "httpx>=0.28" && \
    python -m playwright install chromium --with-deps

COPY hands/ hands/

EXPOSE 8080
CMD ["python", "-m", "hands.server"]
