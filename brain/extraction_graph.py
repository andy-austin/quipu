"""Structured data extraction agent graph."""

import os
from typing import Annotated

from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from brain import graph as graph_module
from brain.extraction_schemas import EXTRACTION_SCHEMAS
from brain.logging import log
from brain.models import get_llm

RECURSION_LIMIT = int(os.getenv("LANGGRAPH_RECURSION_LIMIT", "25"))

EXTRACTION_SYSTEM_PROMPT = (
    "You are a data extraction agent. Your job is to:\n"
    "1. Use the scrape_website tool to fetch the page content.\n"
    "2. Extract structured data from the content.\n"
    "Return ONLY the extracted data, no extra commentary."
)


class ExtractionState(TypedDict):
    messages: Annotated[list, add_messages]
    model: str | None
    user_id: str | None
    url: str
    schema_name: str
    extracted_data: str | None


async def extraction_node(state: ExtractionState) -> ExtractionState:
    """LLM extracts structured data, optionally calling tools first."""
    log.info("extraction_start", url=state.get("url"), schema=state.get("schema_name"))
    llm = get_llm(state.get("model"))
    tools = graph_module.remote_mcp_tools
    if tools:
        llm_with_tools = llm.bind_tools(tools)
    else:
        llm_with_tools = llm

    schema_name = state.get("schema_name", "page")
    schema_cls = EXTRACTION_SCHEMAS.get(schema_name)
    schema_desc = ""
    if schema_cls:
        schema_desc = f"\n\nExtract data matching this schema: {schema_cls.model_json_schema()}"

    system = EXTRACTION_SYSTEM_PROMPT + schema_desc
    response = await llm_with_tools.ainvoke(
        [{"role": "system", "content": system}, *state["messages"]]
    )
    if hasattr(response, "tool_calls") and response.tool_calls:
        log.info("extraction_tool_calls", tools=[tc["name"] for tc in response.tool_calls])
    else:
        log.info("extraction_complete")
    return {"messages": [response]}


async def tool_execution_node(state: ExtractionState) -> ExtractionState:
    """Execute tool calls for extraction (e.g. scrape_website)."""
    from langchain_core.messages import ToolMessage

    last_message = state["messages"][-1]
    tool_map = {t.name: t for t in graph_module.remote_mcp_tools}
    user_id = state.get("user_id")

    new_messages = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        args = dict(tool_call["args"])
        if user_id and tool_name in graph_module._USER_SCOPED_TOOLS:
            args["user_id"] = user_id
        log.info("extraction_tool_executing", tool=tool_name)
        tool = tool_map.get(tool_name)
        if tool is None:
            result = f"Tool '{tool_name}' not found."
        else:
            try:
                result = await tool.ainvoke(args)
                log.info("extraction_tool_success", tool=tool_name)
            except Exception as e:
                result = f"Error executing tool {tool_name}: {e}"
                log.error("extraction_tool_error", tool=tool_name, error=str(e))
        new_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
    return {"messages": new_messages}


async def validate_output_node(state: ExtractionState) -> ExtractionState:
    """Validate the extracted data against the Pydantic schema."""
    last_message = state["messages"][-1]
    content = last_message.content if hasattr(last_message, "content") else ""

    schema_name = state.get("schema_name", "page")
    schema_cls = EXTRACTION_SCHEMAS.get(schema_name)
    if schema_cls and content:
        try:
            import json

            data = json.loads(content) if isinstance(content, str) else content
            validated = schema_cls.model_validate(data)
            log.info("extraction_validated", schema=schema_name)
            return {"extracted_data": validated.model_dump_json()}
        except Exception as e:
            log.warning("extraction_validation_failed", error=str(e))
            return {"extracted_data": content}
    return {"extracted_data": content}


def should_continue(state: ExtractionState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "execute_tools"
    return "validate"


def build_extraction_graph() -> StateGraph:
    builder = StateGraph(ExtractionState)
    builder.add_node("extract", extraction_node)
    builder.add_node("execute_tools", tool_execution_node)
    builder.add_node("validate", validate_output_node)
    builder.add_edge(START, "extract")
    builder.add_conditional_edges("extract", should_continue)
    builder.add_edge("execute_tools", "extract")
    builder.add_edge("validate", END)
    return builder.compile()


extraction_graph = build_extraction_graph()
