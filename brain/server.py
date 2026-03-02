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
from brain.agents.registry import get_agent, list_agents
from brain.chat_graph import chat_graph
from brain.dependencies import verify_user
from brain.extraction_graph import extraction_graph
from brain.graph import RECURSION_LIMIT, agent_graph
from brain.logging import log
from brain.rate_limit import check_rate_limit
from brain.schemas import ChatRequest, ExtractionRequest, ScrapeRequest

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


async def stream_graph(url: str, model: str | None = None, user_id: str | None = None):
    initial_state = {
        "url": url,
        "model": model,
        "user_id": user_id,
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


def _get_mcp_tool(name: str):
    """Look up an MCP tool by name, or return None."""
    for t in graph_module.remote_mcp_tools:
        if t.name == name:
            return t
    return None


async def _load_history(conversation_id: str, user_id: str) -> list[dict]:
    """Load conversation history via the MCP load_conversation tool."""
    tool = _get_mcp_tool("load_conversation")
    if tool is None:
        log.warning("load_conversation_tool_not_found")
        return []
    try:
        result = await tool.ainvoke({"conversation_id": conversation_id, "user_id": user_id})
        if isinstance(result, str):
            result = json.loads(result)
        return result.get("messages", [])
    except Exception as e:
        log.error("load_conversation_failed", error=str(e))
        return []


async def _save_history(conversation_id: str, user_id: str, messages: list[dict]) -> None:
    """Save conversation history via the MCP save_conversation tool."""
    tool = _get_mcp_tool("save_conversation")
    if tool is None:
        log.warning("save_conversation_tool_not_found")
        return
    try:
        await tool.ainvoke(
            {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "messages": messages,
            }
        )
    except Exception as e:
        log.error("save_conversation_failed", error=str(e))


async def stream_chat(
    message: str,
    model: str | None = None,
    user_id: str | None = None,
    system_prompt: str | None = None,
    conversation_id: str | None = None,
):
    # Load history if conversation_id provided
    history: list[dict] = []
    if conversation_id and user_id:
        history = await _load_history(conversation_id, user_id)

    all_messages = history + [{"role": "user", "content": message}]
    initial_state = {
        "model": model,
        "user_id": user_id,
        "system_prompt": system_prompt,
        "conversation_id": conversation_id,
        "messages": all_messages,
    }
    config = {"recursion_limit": RECURSION_LIMIT}
    collected_messages = list(all_messages)
    try:
        async for output in chat_graph.astream(initial_state, config=config):
            for node_name, state_update in output.items():
                messages = state_update.get("messages", [])
                for msg in messages:
                    if isinstance(msg, AIMessage) and msg.content:
                        collected_messages.append({"role": "assistant", "content": msg.content})
                for event in _format_sse_events(node_name, messages):
                    yield _sse_event(event)
        done_event = {"type": "done"}
        if conversation_id:
            done_event["conversation_id"] = conversation_id
        yield _sse_event(done_event)
    except GraphRecursionError:
        msg = "Agent exceeded maximum iterations. Task may be too complex."
        yield _sse_event({"type": "error", "message": msg})
    except Exception as e:
        yield _sse_event({"type": "error", "message": str(e)})

    # Save conversation after streaming
    if conversation_id and user_id:
        await _save_history(conversation_id, user_id, collected_messages)


@app.get("/api/agents")
async def agents_list():
    """List all available agent definitions."""
    return list_agents()


@app.get("/api/chat/stream")
async def chat_stream(params: ChatRequest = Depends()):
    """Unauthenticated chat endpoint — supports chat and scrape agents via SSE."""
    if params.agent == "scrape":
        url = str(params.url) if params.url else ""
        return StreamingResponse(stream_graph(url, params.model), media_type="text/event-stream")

    # Resolve system prompt: explicit param > agent definition > default
    system_prompt = params.system_prompt
    if not system_prompt:
        agent_def = get_agent(params.agent)
        if agent_def and agent_def.system_prompt:
            system_prompt = agent_def.system_prompt

    return StreamingResponse(
        stream_chat(
            params.message,
            params.model,
            system_prompt=system_prompt,
            conversation_id=params.conversation_id,
        ),
        media_type="text/event-stream",
    )


async def stream_extraction(url: str, schema_name: str, model: str | None = None):
    initial_state = {
        "url": url,
        "schema_name": schema_name,
        "model": model,
        "user_id": None,
        "extracted_data": None,
        "messages": [{"role": "user", "content": f"Extract {schema_name} data from: {url}"}],
    }
    config = {"recursion_limit": RECURSION_LIMIT}
    try:
        async for output in extraction_graph.astream(initial_state, config=config):
            for node_name, state_update in output.items():
                messages = state_update.get("messages", [])
                for event in _format_sse_events(node_name, messages):
                    yield _sse_event(event)
                extracted = state_update.get("extracted_data")
                if extracted:
                    yield _sse_event({"type": "extracted", "data": extracted})
        yield _sse_event({"type": "done"})
    except GraphRecursionError:
        msg = "Agent exceeded maximum iterations."
        yield _sse_event({"type": "error", "message": msg})
    except Exception as e:
        yield _sse_event({"type": "error", "message": str(e)})


@app.get("/api/extract/stream")
async def extract_stream(params: ExtractionRequest = Depends()):
    """Extract structured data from a URL via SSE."""
    return StreamingResponse(
        stream_extraction(str(params.url), params.schema_name, params.model),
        media_type="text/event-stream",
    )


@app.get("/api/scraper/stream")
async def process_url(params: ScrapeRequest = Depends(), user_id: str = Depends(verify_user)):
    """Authenticated endpoint that streams LangGraph progression via SSE."""
    check_rate_limit(user_id)
    return StreamingResponse(
        stream_graph(str(params.url), params.model, user_id=user_id),
        media_type="text/event-stream",
    )


@app.get("/api/test/stream")
async def test_stream(params: ScrapeRequest = Depends()):
    """Unauthenticated test endpoint — exercises the full Brain→Hands pipeline."""
    return StreamingResponse(
        stream_graph(str(params.url), params.model), media_type="text/event-stream"
    )


@app.get("/api/runs")
async def runs_list(
    limit: int = 20,
    offset: int = 0,
    user_id: str = Depends(verify_user),
):
    """List past agent runs for the authenticated user with pagination."""
    check_rate_limit(user_id)
    tool = _get_mcp_tool("list_runs")
    if tool is None:
        return {"runs": [], "total": 0}
    result = await tool.ainvoke({"user_id": user_id, "limit": limit, "offset": offset})
    if isinstance(result, str):
        result = json.loads(result)
    return result


@app.get("/api/runs/{run_id}")
async def runs_get(run_id: str, user_id: str = Depends(verify_user)):
    """Retrieve a specific past agent run with full conversation data."""
    check_rate_limit(user_id)
    tool = _get_mcp_tool("get_run")
    if tool is None:
        return {}
    result = await tool.ainvoke({"run_id": run_id, "user_id": user_id})
    if isinstance(result, str):
        result = json.loads(result)
    return result


@app.post("/api/keys")
async def store_key(provider: str, api_key: str, user_id: str = Depends(verify_user)):
    """Store or update a user's API key for a provider."""
    check_rate_limit(user_id)
    tool = _get_mcp_tool("store_api_key")
    if tool is None:
        return {"error": "Key storage not available"}
    result = await tool.ainvoke(
        {
            "user_id": user_id,
            "provider": provider,
            "api_key": api_key,
        }
    )
    if isinstance(result, str):
        result = json.loads(result)
    return result


@app.delete("/api/keys/{provider}")
async def delete_key(provider: str, user_id: str = Depends(verify_user)):
    """Delete a user's API key for a provider."""
    check_rate_limit(user_id)
    tool = _get_mcp_tool("delete_api_key")
    if tool is None:
        return {"error": "Key storage not available"}
    result = await tool.ainvoke({"user_id": user_id, "provider": provider})
    if isinstance(result, str):
        result = json.loads(result)
    return result


@app.get("/api/keys")
async def keys_list(user_id: str = Depends(verify_user)):
    """List all providers for which the user has stored keys."""
    check_rate_limit(user_id)
    tool = _get_mcp_tool("list_api_keys")
    if tool is None:
        return {"providers": []}
    result = await tool.ainvoke({"user_id": user_id})
    if isinstance(result, str):
        result = json.loads(result)
    return result


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mcp_connected": _mcp_connected,
        "tools_loaded": len(graph_module.remote_mcp_tools),
    }
