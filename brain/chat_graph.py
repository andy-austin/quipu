"""General-purpose chat agent graph."""

import os
from typing import Annotated

from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from brain import graph as graph_module
from brain.logging import log
from brain.models import get_llm

RECURSION_LIMIT = int(os.getenv("LANGGRAPH_RECURSION_LIMIT", "25"))

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant. You can use tools when needed "
    "to answer questions or accomplish tasks. Be concise and helpful."
)


class ChatState(TypedDict):
    messages: Annotated[list, add_messages]
    model: str | None
    user_id: str | None
    system_prompt: str | None


async def chat_node(state: ChatState) -> ChatState:
    """LLM generates a response, optionally calling tools."""
    log.info("chat_start")
    llm = get_llm(state.get("model"))
    tools = graph_module.remote_mcp_tools
    if tools:
        llm_with_tools = llm.bind_tools(tools)
    else:
        llm_with_tools = llm

    system_prompt = state.get("system_prompt") or DEFAULT_SYSTEM_PROMPT
    response = await llm_with_tools.ainvoke(
        [{"role": "system", "content": system_prompt}, *state["messages"]]
    )
    if hasattr(response, "tool_calls") and response.tool_calls:
        log.info("chat_tool_calls", tools=[tc["name"] for tc in response.tool_calls])
    else:
        log.info("chat_response_complete")
    return {"messages": [response]}


async def tool_execution_node(state: ChatState) -> ChatState:
    """Execute tool calls returned by the LLM."""
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
        log.info("chat_tool_executing", tool=tool_name)
        tool = tool_map.get(tool_name)
        if tool is None:
            result = f"Tool '{tool_name}' not found."
            log.warning("chat_tool_not_found", tool=tool_name)
        else:
            try:
                result = await tool.ainvoke(args)
                log.info("chat_tool_success", tool=tool_name)
            except Exception as e:
                result = f"Error executing tool {tool_name}: {e}"
                log.error("chat_tool_error", tool=tool_name, error=str(e))

        new_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
    return {"messages": new_messages}


def should_continue(state: ChatState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "execute_tools"
    return END


def build_chat_graph() -> StateGraph:
    builder = StateGraph(ChatState)
    builder.add_node("chat", chat_node)
    builder.add_node("execute_tools", tool_execution_node)
    builder.add_edge(START, "chat")
    builder.add_conditional_edges("chat", should_continue)
    builder.add_edge("execute_tools", "chat")
    return builder.compile()


chat_graph = build_chat_graph()
