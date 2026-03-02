"""Multi-Hands MCP registry — connects to multiple MCP servers and routes tools."""

import asyncio
import json
import os

from langchain_mcp_adapters.client import MultiServerMCPClient

from brain.logging import log

MCP_MAX_RETRIES = int(os.getenv("MCP_MAX_RETRIES", "5"))
MCP_RETRY_BASE_DELAY = float(os.getenv("MCP_RETRY_BASE_DELAY", "1.0"))


class MCPRegistry:
    """Manages connections to multiple MCP (Hands) servers.

    Each server is identified by a name and provides a set of tools.
    Tools are merged into a single flat list for LLM binding, with
    server origin tracked for health monitoring.
    """

    def __init__(self) -> None:
        self.servers: dict[str, dict] = {}  # name -> {url, tools, healthy}
        self._all_tools: list = []

    @property
    def tools(self) -> list:
        """All tools from all connected servers."""
        return self._all_tools

    @property
    def connected(self) -> bool:
        return any(s["healthy"] for s in self.servers.values())

    @property
    def status(self) -> dict:
        return {
            name: {
                "url": info["url"],
                "healthy": info["healthy"],
                "tools": [t.name for t in info["tools"]],
            }
            for name, info in self.servers.items()
        }

    async def connect(self, name: str, url: str) -> bool:
        """Connect to a single MCP server with exponential backoff."""
        for attempt in range(1, MCP_MAX_RETRIES + 1):
            try:
                client = MultiServerMCPClient({name: {"transport": "sse", "url": url}})
                tools = await client.get_tools()
                self.servers[name] = {"url": url, "tools": tools, "healthy": True}
                self._rebuild_tools()
                log.info(
                    "mcp_server_connected",
                    name=name,
                    attempt=attempt,
                    tools=[t.name for t in tools],
                )
                return True
            except Exception as e:
                delay = MCP_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                log.warning(
                    "mcp_server_connection_failed",
                    name=name,
                    attempt=attempt,
                    max=MCP_MAX_RETRIES,
                    error=str(e),
                )
                if attempt < MCP_MAX_RETRIES:
                    await asyncio.sleep(delay)

        self.servers[name] = {"url": url, "tools": [], "healthy": False}
        log.error("mcp_server_connection_exhausted", name=name)
        return False

    async def connect_all(self) -> None:
        """Connect to all configured MCP servers.

        Config is read from MCP_SERVERS env var as JSON:
        [{"name": "default", "url": "http://..."}, ...]

        Falls back to MCP_SERVER_URL for single-server backward compat.
        """
        servers_json = os.getenv("MCP_SERVERS", "")
        if servers_json:
            try:
                servers = json.loads(servers_json)
            except json.JSONDecodeError:
                log.error("mcp_servers_invalid_json")
                servers = []
        else:
            # Backward compatibility: single server
            url = os.getenv("MCP_SERVER_URL", "http://localhost:8080/sse")
            servers = [{"name": "default", "url": url}]

        tasks = [self.connect(s["name"], s["url"]) for s in servers]
        await asyncio.gather(*tasks)

    async def health_check(self, name: str) -> bool:
        """Re-check a server's health by attempting to reconnect."""
        info = self.servers.get(name)
        if not info:
            return False
        return await self.connect(name, info["url"])

    async def health_check_all(self) -> dict:
        """Health-check all unhealthy servers."""
        results = {}
        for name, info in self.servers.items():
            if not info["healthy"]:
                results[name] = await self.health_check(name)
            else:
                results[name] = True
        return results

    def _rebuild_tools(self) -> None:
        """Rebuild the flat tool list from all healthy servers."""
        self._all_tools = []
        seen = set()
        for info in self.servers.values():
            if info["healthy"]:
                for tool in info["tools"]:
                    if tool.name not in seen:
                        self._all_tools.append(tool)
                        seen.add(tool.name)


# Global singleton
registry = MCPRegistry()
