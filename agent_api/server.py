import json
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse
from langchain_mcp_adapters.client import MultiServerMCPClient

from agent_api.dependencies import verify_user
from agent_api import graph as graph_module
from agent_api.graph import agent_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    mcp_url = os.getenv("MCP_SERVER_URL", "http://localhost:8080/sse")

    client = MultiServerMCPClient(
        {"mcp_tools": {"transport": "sse", "url": mcp_url}}
    )
    graph_module.remote_mcp_tools = await client.get_tools()
    print(f"Loaded remote tools: {[t.name for t in graph_module.remote_mcp_tools]}")

    yield


app = FastAPI(title="Agent API", lifespan=lifespan)


async def stream_graph(url: str):
    initial_state = {"url": url, "messages": [{"role": "user", "content": f"Process URL: {url}"}]}
    async for output in agent_graph.astream(initial_state):
        for node_name, state_update in output.items():
            messages = state_update.get("messages", [])
            log_entries = [
                m.content if hasattr(m, "content") else str(m) for m in messages
            ]
            payload = {"step": node_name, "logs": log_entries}
            yield f"data: {json.dumps(payload)}\n\n"
    yield f"data: {json.dumps({'step': 'END'})}\n\n"


@app.get("/api/scraper/stream")
async def process_url(url: str, user_id: str = Depends(verify_user)):
    """Authenticated endpoint that streams LangGraph progression via SSE."""
    return StreamingResponse(stream_graph(url), media_type="text/event-stream")


@app.get("/health")
async def health():
    return {"status": "ok"}
