"""
Server-related tool registration helpers.

Contains the tool registration functions for Superset server management:
- list_superset_servers
- superset_reauthenticate
- superset_server_status
"""
from typing import Optional
from fastmcp import FastMCP

from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools import server


def register_server_tools(mcp: FastMCP, manager: ConnectionManager) -> None:
    """Register all server management tools with the FastMCP instance.

    Args:
        mcp: The FastMCP instance to register tools with.
        manager: The initialized ConnectionManager instance.
    """

    @mcp.tool(name="list_superset_servers")
    async def tool_list_servers() -> str:
        """Lists all configured Superset servers."""
        return await server.list_servers(manager)

    @mcp.tool(name="superset_reauthenticate")
    async def tool_reauthenticate(server_id: str) -> str:
        """Forces re-authentication with a Superset server."""
        return await server.reauthenticate(manager, server_id)

    @mcp.tool(name="superset_server_status")
    async def tool_server_status(server_id: str) -> str:
        """Checks the status and connectivity of a specific Superset server."""
        return await server.server_status(manager, server_id)
