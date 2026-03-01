from typing import Annotated, Optional
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

# Populated at startup from the MCP tool server
remote_mcp_tools: list = []


class AgentState(TypedDict):
    url: str
    db_status: Optional[str]
    raw_content: Optional[str]
    final_json: Optional[str]
    messages: Annotated[list, add_messages]


async def scrape_decision_node(state: AgentState) -> AgentState:
    """LLM decides whether to scrape based on tools and current state."""
    llm = ChatOpenAI(model="gpt-4o")
    llm_with_tools = llm.bind_tools(remote_mcp_tools)

    system_prompt = (
        "You are a web scraping agent. Given a URL, first check if fresh data "
        "already exists in the database. If it does, return the cached result. "
        "Otherwise, scrape the website and save the metadata."
    )
    response = await llm_with_tools.ainvoke(
        [{"role": "system", "content": system_prompt}, *state["messages"]]
    )
    return {"messages": [response]}


async def tool_execution_node(state: AgentState) -> AgentState:
    """Execute tool calls returned by the LLM."""
    from langchain_core.messages import ToolMessage

    last_message = state["messages"][-1]
    tool_map = {t.name: t for t in remote_mcp_tools}

    results = []
    for tool_call in last_message.tool_calls:
        tool = tool_map.get(tool_call["name"])
        if tool is None:
            result = f"Tool '{tool_call['name']}' not found."
        else:
            result = await tool.ainvoke(tool_call["args"])
        results.append(
            ToolMessage(content=str(result), tool_call_id=tool_call["id"])
        )
    return {"messages": results}


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
