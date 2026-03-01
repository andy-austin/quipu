FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml .
RUN uv pip install --system -e . && \
    python -m playwright install chromium --with-deps

COPY . .

EXPOSE 8080
CMD ["python", "-m", "mcp_server.server"]
