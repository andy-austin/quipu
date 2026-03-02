import asyncio
import atexit
import os

from mcp.server.fastmcp import FastMCP

from hands.tools.conversation_tools import load_conversation, save_conversation
from hands.tools.db_tools import check_database_freshness, close_pool, save_metadata
from hands.tools.key_tools import delete_api_key, list_api_keys, store_api_key
from hands.tools.run_tools import get_run, list_runs, save_run
from hands.tools.web_tools import scrape_website

port = int(os.getenv("PORT", "8080"))
mcp = FastMCP("WebScrapingTools", host="0.0.0.0", port=port)

mcp.tool()(check_database_freshness)
mcp.tool()(scrape_website)
mcp.tool()(save_metadata)
mcp.tool()(load_conversation)
mcp.tool()(save_conversation)
mcp.tool()(list_runs)
mcp.tool()(get_run)
mcp.tool()(save_run)
mcp.tool()(store_api_key)
mcp.tool()(delete_api_key)
mcp.tool()(list_api_keys)


def _shutdown_pool() -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(close_pool())
    except RuntimeError:
        asyncio.run(close_pool())


atexit.register(_shutdown_pool)

if __name__ == "__main__":
    mcp.run(transport="sse")
