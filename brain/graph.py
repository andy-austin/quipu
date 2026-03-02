import os
from typing import Annotated

from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from brain.logging import log
from brain.models import get_llm

# Populated at startup from the MCP tool server
remote_mcp_tools: list = []

RECURSION_LIMIT = int(os.getenv("LANGGRAPH_RECURSION_LIMIT", "25"))


class AgentState(TypedDict):
    url: str
    model: str | None
    user_id: str | None
    db_status: str | None
    raw_content: str | None
    final_json: str | None
    messages: Annotated[list, add_messages]


async def scrape_decision_node(state: AgentState) -> AgentState:
    """LLM decides whether to scrape based on tools and current state."""
    log.info("reasoning_start", url=state.get("url"))
    llm = get_llm(state.get("model"))
    llm_with_tools = llm.bind_tools(remote_mcp_tools)

    system_prompt = (
        "You are a web scraping agent. Follow these steps exactly:\n"
        "1. Call 'check_database_freshness' for the given URL.\n"
        "2. If fresh data exists, return it and stop.\n"
        "3. If no fresh data exists, call 'scrape_website'.\n"
        "4. Once you have the scraped data, call 'save_metadata' to persist it.\n"
        "5. Finally, return the scraped results.\n"
        "Do NOT call 'scrape_website' and 'save_metadata' in the same turn."
    )
    response = await llm_with_tools.ainvoke(
        [{"role": "system", "content": system_prompt}, *state["messages"]]
    )
    if hasattr(response, "tool_calls") and response.tool_calls:
        log.info("tool_calls_requested", tools=[tc["name"] for tc in response.tool_calls])
    else:
        log.info("reasoning_complete", tool_calls=False)
    return {"messages": [response]}


# Tools that receive user_id for data isolation
_USER_SCOPED_TOOLS = {"check_database_freshness", "save_metadata"}


async def tool_execution_node(state: AgentState) -> AgentState:
    """Execute tool calls returned by the LLM."""
    from langchain_core.messages import ToolMessage

    last_message = state["messages"][-1]
    tool_map = {t.name: t for t in remote_mcp_tools}
    user_id = state.get("user_id")

    new_messages = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        args = dict(tool_call["args"])
        # Inject user_id into user-scoped tools for data isolation
        if user_id and tool_name in _USER_SCOPED_TOOLS:
            args["user_id"] = user_id
        log.info("tool_executing", tool=tool_name, args=args)
        tool = tool_map.get(tool_name)
        if tool is None:
            result = f"Tool '{tool_name}' not found."
            log.warning("tool_not_found", tool=tool_name)
        else:
            try:
                # Sequential execution to avoid MCP session/browser closure issues
                result = await tool.ainvoke(args)
                log.info("tool_success", tool=tool_name)
            except Exception as e:
                result = f"Error executing tool {tool_name}: {e}"
                log.error("tool_error", tool=tool_name, error=str(e))

        new_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call["id"]))
    return {"messages": new_messages}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "execute_tools"
    return END


def build_graph() -> StateGraph:
    builder = StateGraph(AgentState)
    builder.add_node("reasoning", scrape_decision_node)
    builder.add_node("execute_tools", tool_execution_node)
    builder.add_edge(START, "reasoning")
    builder.add_conditional_edges("reasoning", should_continue)
    builder.add_edge("execute_tools", "reasoning")
    return builder.compile()


agent_graph = build_graph()
