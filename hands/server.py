import os

from mcp.server.fastmcp import FastMCP

from hands.tools.db_tools import check_database_freshness, save_metadata
from hands.tools.web_tools import scrape_website

port = int(os.getenv("PORT", "8080"))
mcp = FastMCP("WebScrapingTools", host="0.0.0.0", port=port)

mcp.tool()(check_database_freshness)
mcp.tool()(scrape_website)
mcp.tool()(save_metadata)

if __name__ == "__main__":
    mcp.run(transport="sse")
