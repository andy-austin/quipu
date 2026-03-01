FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml .
RUN uv pip install --system -e .

COPY . .

EXPOSE 8000
CMD ["uvicorn", "agent_api.server:app", "--host", "0.0.0.0", "--port", "8000"]
