import os

from mcp.server.fastmcp import FastMCP

from mcp_server.tools.db_tools import check_database_freshness, save_metadata
from mcp_server.tools.web_tools import scrape_website

mcp = FastMCP("WebScrapingTools")

mcp.tool()(check_database_freshness)
mcp.tool()(scrape_website)
mcp.tool()(save_metadata)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
