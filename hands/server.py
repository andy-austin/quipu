import asyncio
import atexit
import os

from mcp.server.fastmcp import FastMCP

from hands.tools.conversation_tools import load_conversation, save_conversation
from hands.tools.db_tools import check_database_freshness, close_pool, save_metadata
from hands.tools.file_tools import list_files, parse_document, upload_file
from hands.tools.key_tools import delete_api_key, list_api_keys, store_api_key
from hands.tools.notification_tools import send_email, send_slack_message, send_webhook
from hands.tools.run_tools import get_run, list_runs, save_run
from hands.tools.web_tools import scrape_website
from hands.tools.webhook_tools import create_webhook, delete_webhook, get_webhook, list_webhooks

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
mcp.tool()(send_email)
mcp.tool()(send_slack_message)
mcp.tool()(send_webhook)
mcp.tool()(create_webhook)
mcp.tool()(list_webhooks)
mcp.tool()(get_webhook)
mcp.tool()(delete_webhook)
mcp.tool()(upload_file)
mcp.tool()(parse_document)
mcp.tool()(list_files)


def _shutdown_pool() -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(close_pool())
    except RuntimeError:
        asyncio.run(close_pool())


atexit.register(_shutdown_pool)

if __name__ == "__main__":
    mcp.run(transport="sse")
