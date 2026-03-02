import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.errors import GraphRecursionError

from brain import graph as graph_module
from brain.dependencies import verify_user
from brain.graph import RECURSION_LIMIT, agent_graph
from brain.logging import log
from brain.schemas import ScrapeRequest

MCP_MAX_RETRIES = int(os.getenv("MCP_MAX_RETRIES", "5"))
MCP_RETRY_BASE_DELAY = float(os.getenv("MCP_RETRY_BASE_DELAY", "1.0"))

_mcp_connected = False


async def _connect_mcp(mcp_url: str) -> None:
    """Connect to MCP server with exponential backoff."""
    global _mcp_connected
    for attempt in range(1, MCP_MAX_RETRIES + 1):
        try:
            client = MultiServerMCPClient({"mcp_tools": {"transport": "sse", "url": mcp_url}})
            graph_module.remote_mcp_tools = await client.get_tools()
            _mcp_connected = True
            log.info(
                "mcp_connected",
                attempt=attempt,
                tools=[t.name for t in graph_module.remote_mcp_tools],
            )
            return
        except Exception as e:
            delay = MCP_RETRY_BASE_DELAY * (2 ** (attempt - 1))
            log.warning("mcp_connection_failed", attempt=attempt, max=MCP_MAX_RETRIES, error=str(e))
            if attempt < MCP_MAX_RETRIES:
                log.info("mcp_retrying", delay=delay)
                await asyncio.sleep(delay)
    _mcp_connected = False
    log.error("mcp_connection_exhausted")


@asynccontextmanager
async def lifespan(app: FastAPI):
    mcp_url = os.getenv("MCP_SERVER_URL", "http://localhost:8080/sse")
    await _connect_mcp(mcp_url)
    yield


app = FastAPI(title="Brain", lifespan=lifespan)

_cors_raw = os.getenv("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _sse_event(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _format_sse_events(node_name: str, messages: list) -> list[dict]:
    """Map LangGraph node outputs to structured SSE events."""
    events = []
    for msg in messages:
        if isinstance(msg, AIMessage):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    events.append(
                        {
                            "type": "tool_start",
                            "message": f"Calling {tc['name']}...",
                            "tool": tc["name"],
                        }
                    )
            elif msg.content:
                events.append(
                    {
                        "type": "reasoning" if node_name == "reasoning" else "answer",
                        "message": msg.content,
                    }
                )
        elif isinstance(msg, ToolMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            is_error = content.startswith("Error")
            events.append(
                {
                    "type": "tool_result",
                    "message": content[:200],
                    "tool": msg.name or "",
                    "status": "error" if is_error else "success",
                }
            )
    return events


async def stream_graph(url: str, model: str | None = None):
    initial_state = {
        "url": url,
        "model": model,
        "messages": [{"role": "user", "content": f"Process URL: {url}"}],
    }
    config = {"recursion_limit": RECURSION_LIMIT}
    try:
        async for output in agent_graph.astream(initial_state, config=config):
            for node_name, state_update in output.items():
                messages = state_update.get("messages", [])
                for event in _format_sse_events(node_name, messages):
                    yield _sse_event(event)
        yield _sse_event({"type": "done"})
    except GraphRecursionError:
        msg = "Agent exceeded maximum iterations. Task may be too complex."
        yield _sse_event({"type": "error", "message": msg})
    except Exception as e:
        yield _sse_event({"type": "error", "message": str(e)})


@app.get("/api/scraper/stream")
async def process_url(params: ScrapeRequest = Depends(), user_id: str = Depends(verify_user)):
    """Authenticated endpoint that streams LangGraph progression via SSE."""
    return StreamingResponse(
        stream_graph(str(params.url), params.model), media_type="text/event-stream"
    )


@app.get("/api/test/stream")
async def test_stream(params: ScrapeRequest = Depends()):
    """Unauthenticated test endpoint — exercises the full Brain→Hands pipeline."""
    return StreamingResponse(
        stream_graph(str(params.url), params.model), media_type="text/event-stream"
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mcp_connected": _mcp_connected,
        "tools_loaded": len(graph_module.remote_mcp_tools),
    }
