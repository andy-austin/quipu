# Quipu

A decentralized AI agent system that separates **reasoning** from **execution**. The Brain orchestrates LLM-powered agents while the Hands expose tools as typed, standardized MCP services — allowing each layer to scale independently.

## Architecture

```
┌─────────────────────┐       SSE (Fly .internal)       ┌─────────────────────┐
│       Brain          │◄──────────────────────────────►│        Hands         │
│  FastAPI + LangGraph │        MCP Protocol             │  FastMCP Tool Server │
│  Port 8000 (public)  │                                 │  Port 8080 (private) │
└──────────┬──────────┘                                 └──────────┬──────────┘
           │                                                       │
     Supabase JWT                                          ┌───────┴───────┐
     Authentication                                        │               │
                                                      Supabase DB    Target Websites
                                                      (PostgreSQL)   (httpx/Playwright)
```

**Brain** (`brain/`) — The reasoning engine. On startup it connects to the Hands service via MCP, discovers available tools, and binds them to a LangGraph state machine. Agents use an LLM to decide which tools to invoke, then stream results back to clients via SSE.

**Hands** (`hands/`) — The tool server. Knows nothing about AI, prompts, or agents. It exposes pure Python functions (database queries, web scraping) as typed MCP tools over SSE. New tools are added here and automatically discovered by the Brain.

### Tech Stack

| Layer | Technology |
|---|---|
| Brain | FastAPI, LangGraph, langchain-mcp-adapters, Gemini |
| Hands | FastMCP, asyncpg, Playwright |
| Auth & DB | Supabase (PostgreSQL + JWT) |
| Web Scraping | httpx + BeautifulSoup (with Playwright headless fallback) |
| Deployment | Fly.io (private IPv6 networking between services) |

> The frontend (Next.js on Vercel) lives in a separate repository.

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- [just](https://github.com/casey/just) (`brew install just`)

### Installation

```bash
git clone https://github.com/andy-austin/quipu.git
cd quipu
uv sync
```

### Environment Variables

Copy the example and fill in your values:

```bash
cp .env.example .env
```

See `.env.example` for all required variables (`GOOGLE_API_KEY`, `SUPABASE_JWT_SECRET`, `SUPABASE_DB_URL`, etc.).

### Running Locally

```bash
just dev
```

This starts the Hands tool server (port 8080) then the Brain (port 8000 with hot-reload) in a single terminal. The Brain connects to the Hands on startup and discovers available tools automatically.

You can also run them individually with `just brain` and `just hands`.

## Project Structure

```
quipu/
├── brain/                   # The Brain — LLM orchestration
│   ├── server.py            # FastAPI app, MCP client, SSE streaming
│   ├── graph.py             # LangGraph state machine (reasoning ↔ tool execution)
│   ├── dependencies.py      # Supabase JWT auth middleware
│   ├── Dockerfile
│   └── fly.toml
├── hands/                   # The Hands — MCP tool server
│   ├── server.py            # FastMCP initialization and tool registration
│   ├── tools/
│   │   ├── db_tools.py      # Database freshness checks, metadata persistence
│   │   └── web_tools.py     # Web scraping (httpx + Playwright fallback)
│   ├── Dockerfile
│   └── fly.toml
├── docs/
│   └── architecture.md      # Full architecture guide with Mermaid diagrams
└── pyproject.toml           # uv workspace root
```

## Development

```bash
just lint                # check lint and formatting
just fix                 # auto-fix lint and formatting
just typecheck           # run pyright
just test                # run all tests
just health              # curl the health endpoint
```

## Deployment

Both services deploy to Fly.io as isolated apps. The Hands service runs on Fly's private network (no public IP); the Brain is publicly exposed over HTTPS.

```bash
# Deploy Hands
cd hands && fly deploy

# Deploy Brain
cd brain && fly deploy
```

The Brain reaches the Hands service via Fly's internal DNS (`http://your-hands.internal:8080/sse`), keeping all tool traffic off the public internet.

## Adding New Tools

1. Create a function in `hands/tools/` (or add to an existing module)
2. Register it in `hands/server.py` with `mcp.tool()(your_function)`
3. Restart both services — the Brain discovers the new tool automatically via MCP

No changes to the Brain are needed. The LLM will see the new tool's name, description, and type signature and can invoke it immediately.

## Adding New Agents

1. Define a new `AgentState` and LangGraph graph in `brain/`
2. Add a new streaming endpoint in `brain/server.py`
3. The new agent shares the existing MCP tool discovery and JWT auth infrastructure

## License

MIT
