# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Quipu is a decentralized AI agent system built as a uv workspace monorepo with two microservices:

- **Brain** (`brain/`) — FastAPI + LangGraph reasoning engine that orchestrates LLM calls and manages agent state. Connects to the Hands service via MCP to discover available tools at startup.
- **Hands** (`hands/`) — FastMCP tool server that exposes typed Python functions (database, web scraping) over SSE. Has zero knowledge of AI/LLM concerns.

The Brain and Hands communicate over Fly.io's private IPv6 network using SSE. The Brain is an MCP client; the Hands is an MCP server. See `docs/architecture.md` for the full architecture diagram and deployment strategy.

## Build & Development Commands

```bash
# Install all workspace dependencies
uv sync

# Run the Brain (port 8000)
uvicorn brain.server:app --host 0.0.0.0 --port 8000

# Run the Hands tool server (port 8080)
python -m hands.server

# Lint
ruff check .
ruff format --check .

# Type check
pyright

# Tests
pytest                        # all tests
pytest brain/                 # single package
pytest -k test_name           # single test
```

## Code Quality

- Python 3.12+, enforced via `.python-version`
- Ruff: line-length 100, rules `E, F, I, UP`
- Pyright: basic mode
- pytest with `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed)

## Architecture Details

**Brain startup lifecycle** (`brain/server.py`): The FastAPI lifespan connects to the Hands MCP server once, fetches all available tools, and stores them in `graph_module.remote_mcp_tools`. The LangGraph graph (`brain/graph.py`) binds these tools to the LLM at inference time.

**LangGraph flow** (`brain/graph.py`): `reasoning` node → conditional edge → `execute_tools` node → loops back to `reasoning`. The `should_continue` function checks for tool calls to decide whether to execute tools or end.

**Tool registration** (`hands/server.py`): Functions in `hands/tools/` are registered via `mcp.tool()()` decorator pattern on the FastMCP instance.

**Auth** (`brain/dependencies.py`): All Brain endpoints require a Supabase JWT. The `verify_user` dependency decodes the token and extracts `user_id`.

## Environment Variables

Brain: `OPENAI_API_KEY`, `SUPABASE_JWT_SECRET`, `MCP_SERVER_URL`
Hands: `SUPABASE_DB_URL`, `BROWSERLESS_API_KEY`

## Deployment

Both services deploy to Fly.io as separate apps with their own `fly.toml` and `Dockerfile`. The Hands service is internal-only (no public IP); the Brain is publicly exposed over HTTPS.
