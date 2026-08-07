"""
System and metadata tool registration helpers.

Contains the tool registration functions for Superset system operations:
- get_schema
- get_instance_info
- health_check
- list_databases
- get_database_info
- superset_available_resource_types
- superset_list_resources
- list_dashboards
- superset_get_resource
"""
from typing import List, Optional, Union
from fastmcp import FastMCP

from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools import resources
from modules.SupersetModule.tools import databases
from modules.SupersetModule.tools import system


def register_system_tools(mcp: FastMCP, manager: ConnectionManager) -> None:
    """Register all system/metadata tools with the FastMCP instance.

    Args:
        mcp: The FastMCP instance to register tools with.
        manager: The initialized ConnectionManager instance.
    """

    @mcp.tool(name="superset_available_resource_types")
    async def tool_list_resource_types() -> str:
        """Lists all available resource types for superset_list_resources."""
        return await resources.list_resource_types()

    @mcp.tool(name="superset_list_resources")
    async def tool_list_resources(server_id: str, resource_type: str) -> str:
        """Lists resources of a specific type. Wrapper around GET /api/v1/{resource_type}/."""
        return await resources.list_resources(manager, server_id, resource_type)

    @mcp.tool(name="list_dashboards")
    async def tool_list_dashboards(server_id: str) -> str:
        """Lists dashboards on a specific server to get their IDs."""
        return await resources.list_dashboards(manager, server_id)

    @mcp.tool(name="superset_get_resource")
    async def tool_get_resource(server_id: str, resource_type: str, resource_id: Union[int, str]) -> str:
        """Gets details for a specific resource by ID. Wrapper around GET /api/v1/{resource_type}/{pk}."""
        return await resources.get_resource(manager, server_id, resource_type, resource_id)

    @mcp.tool(name="list_databases")
    async def tool_list_databases(server_id: str) -> str:
        """Lists all database connections. GET /api/v1/database/."""
        return await databases.list_databases(manager, server_id)

    @mcp.tool(name="get_database_info")
    async def tool_get_database_info(server_id: str, database_id: int) -> str:
        """Gets detailed information for a specific database connection by ID."""
        return await databases.get_database_info(manager, server_id, database_id)

    @mcp.tool(name="get_schema")
    async def tool_get_schema(server_id: str, model_type: Optional[str] = None) -> str:
        """Get schema metadata (filterable/sortable columns) for chart/dataset/dashboard/database."""
        return await system.get_schema(manager, server_id, model_type)

    @mcp.tool(name="get_instance_info")
    async def tool_get_instance_info(server_id: str) -> str:
        """Get instance info: user identity, feature flags, metadata."""
        return await system.get_instance_info(manager, server_id)

    @mcp.tool(name="health_check")
    async def tool_health_check(server_id: str) -> str:
        """Check the health status of a Superset server."""
        return await system.health_check(manager, server_id)
