"""
Main register() function for Superset MCP tool registration.

This module serves as the main entry point for registering all Superset MCP
tools. It delegates to grouped submodules for tool organization.

Tools are organized into logical groups:
- Server management (server_tools)
- Resource discovery (system_tools)
- Chart operations (chart_tools)
- Dashboard operations (dashboard_tools)
- Dataset operations (dataset_tools)
- SQL Lab (sqllab_tools)
- Transfer and explore (tools.py)
- Semantic and profiling (system_tools)
"""
import os
import sys
import logging
from typing import Optional

from fastapi import Query
from fastmcp import FastMCP
from modules.registry import ModuleRegistry

from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.registry.grouped.server_tools import register_server_tools
from modules.SupersetModule.tools.registry.grouped.chart_tools import register_chart_tools
from modules.SupersetModule.tools.registry.grouped.dashboard_tools import register_dashboard_tools
from modules.SupersetModule.tools.registry.grouped.dataset_tools import register_dataset_tools
from modules.SupersetModule.tools.registry.grouped.sqllab_tools import register_sqllab_tools
from modules.SupersetModule.tools.registry.grouped.system_tools import register_system_tools
from modules.SupersetModule.tools.registry.tools import register_explore_tools, register_transfer_tools

# Configure structured logging with timestamp, module name, and log level
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)


def get_module_api():
    """Return a dictionary of internal APIs for inter-module communication.

    Provides programmatic access to core SupersetModule functionality that other
    modules may need, including the ConnectionManager class and key request helpers.

    Returns:
        Dictionary mapping API names to their callable implementations:
        - "ConnectionManager": The ConnectionManager class for creating new contexts
        - "api_request": The superset API request handler function
        - "execute_request": The authenticated HTTP request executor with token refresh
    """
    return {
        "ConnectionManager": ConnectionManager,
        "api_request": __import__("modules.SupersetModule.tools.general", fromlist=["impl_superset_api"]).impl_superset_api,
        "execute_request": __import__("modules.SupersetModule.api_client", fromlist=["execute_request"]).execute_request,
    }


def register(mcp: FastMCP, registry: Optional[ModuleRegistry] = None) -> None:
    """Register all Superset MCP tools and initialize the connection manager.

    This is the main entry point called by the MCP server during startup. It
    creates a ConnectionManager, loads server configurations, and registers
    all tool handlers with the FastMCP instance.

    Args:
        mcp: The FastMCP instance to register tools with. Tools are bound
            to this instance and become available to the LLM.
        registry: Optional ModuleRegistry for inter-module API exposure.
            If provided, the module's internal API dictionary is registered
            under the key "SupersetModule".
    """
    # Resolve the module's directory path for config file resolution
    module_dir = os.path.dirname(__file__)
    # Create and initialize the connection manager with server configurations
    manager = ConnectionManager(module_dir)
    manager.load_servers()

    # Register all tool groups
    register_server_tools(mcp, manager)
    register_chart_tools(mcp, manager)
    register_dashboard_tools(mcp, manager)
    register_dataset_tools(mcp, manager)
    register_sqllab_tools(mcp, manager)
    register_system_tools(mcp, manager)
    register_transfer_tools(mcp, manager)
    register_explore_tools(mcp, manager)

    # Register semantic and profiling tools
    _register_semantic_tools(mcp, manager)

    # Register internal module API for inter-module communication
    if registry is not None:
        registry.register_module_api("SupersetModule", get_module_api())


def _register_semantic_tools(mcp: FastMCP, manager: ConnectionManager) -> None:
    """Register semantic layer and data profiling tools.

    Args:
        mcp: The FastMCP instance to register tools with.
        manager: The initialized ConnectionManager instance.
    """
    from modules.SupersetModule.tools import semantic

    @mcp.tool(name="profile_table")
    async def tool_profile_table(server_id: str, database_id: int, schema: str, table: str) -> str:
        """Profile a database table: row count, column stats, nulls, distinct, min/max/avg, stddev, top values."""
        return await semantic.profile_table(manager, server_id, database_id, schema, table)

    @mcp.tool(name="suggest_metrics")
    async def tool_suggest_metrics(server_id: str, database_id: int, schema: str, table: str) -> str:
        """Auto-suggest aggregate metrics (SUM, AVG, COUNT, MIN, MAX) for numeric columns."""
        return await semantic.suggest_metrics(manager, server_id, database_id, schema, table)

    @mcp.tool(name="suggest_dimensions")
    async def tool_suggest_dimensions(server_id: str, database_id: int, schema: str, table: str) -> str:
        """Auto-suggest dimension columns (text/categorical/date/boolean) for grouping and filtering."""
        return await semantic.suggest_dimensions(manager, server_id, database_id, schema, table)

    @mcp.tool(name="get_data_dictionary")
    async def tool_get_data_dictionary(server_id: str, database_id: int, schema: str, table: str, include_statistics: bool = True) -> str:
        """Generate a data dictionary for a table: column names, types, categories, recommended roles, and optional statistics."""
        return await semantic.get_data_dictionary(manager, server_id, database_id, schema, table, include_statistics)
