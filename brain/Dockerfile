FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN uv pip install --system --no-cache \
    "fastapi>=0.115" "uvicorn[standard]>=0.34" "langgraph>=0.3" \
    "langchain-mcp-adapters>=0.1" "langchain-google-genai>=2.1" \
    "python-jose[cryptography]>=3.3" "supabase>=2.10" "httpx>=0.28"

COPY brain/ brain/

EXPOSE 8000
CMD ["uvicorn", "brain.server:app", "--host", "0.0.0.0", "--port", "8000"]
