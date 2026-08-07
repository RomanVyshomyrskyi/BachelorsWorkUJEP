"""
Tool registration helpers and wrapper functions.

Provides helper utilities for tool registration and wrappers for tools
that need special handling (like the explore and transfer tools).
"""
from typing import List, Optional
from fastmcp import FastMCP

from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools import transfer
from modules.SupersetModule.tools import explore


def register_transfer_tools(mcp: FastMCP, manager: ConnectionManager) -> None:
    """Register transfer tools with the FastMCP instance.

    Args:
        mcp: The FastMCP instance to register tools with.
        manager: The initialized ConnectionManager instance.
    """

    @mcp.tool(name="transfer_dashboard")
    async def tool_transfer_dashboard(source_server_id: str, target_server_id: str, dashboard_id: int, db_mappings: Optional[str] = None, table_mappings: Optional[str] = None) -> str:
        """Transfers a dashboard (and its charts) between servers. 3-phase: datasets→charts→dashboard. Returns NEED_INPUT if mappings required."""
        return await transfer.transfer_dashboard(manager, source_server_id, target_server_id, dashboard_id, db_mappings, table_mappings)


def register_explore_tools(mcp: FastMCP, manager: ConnectionManager) -> None:
    """Register explore tools with the FastMCP instance.

    Args:
        mcp: The FastMCP instance to register tools with.
        manager: The initialized ConnectionManager instance.
    """

    @mcp.tool(name="generate_explore_link")
    async def tool_generate_explore_link(server_id: str, dataset_id: int, config: Optional[str] = None) -> str:
        """Generate interactive explore URL. Does NOT create a permanent chart."""
        return await explore.generate_explore_link(manager, server_id, dataset_id, config)
