"""
Dataset-related tool registration helpers.

Contains the tool registration functions for Superset dataset operations:
- superset_create_dataset
- list_datasets
- get_dataset_info
- create_virtual_dataset
- superset_get_database_schema
"""
from typing import List, Optional
from fastmcp import FastMCP

from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools import datasets


def register_dataset_tools(mcp: FastMCP, manager: ConnectionManager) -> None:
    """Register all dataset tools with the FastMCP instance.

    Args:
        mcp: The FastMCP instance to register tools with.
        manager: The initialized ConnectionManager instance.
    """

    @mcp.tool(name="superset_create_dataset")
    async def tool_create_dataset(server_id: str, table_name: str, database_id: int, schema: Optional[str] = None, owners: Optional[List[int]] = None, metrics_json: Optional[str] = None, columns_json: Optional[str] = None, sql_expression: Optional[str] = None) -> str:
        """Creates a new dataset on a Superset server."""
        return await datasets.create_dataset(manager, server_id, table_name, database_id, schema, owners, metrics_json, columns_json, sql_expression)

    @mcp.tool(name="list_datasets")
    async def tool_list_datasets(server_id: str) -> str:
        """Lists all datasets. GET /api/v1/dataset/."""
        return await datasets.list_datasets(manager, server_id)

    @mcp.tool(name="get_dataset_info")
    async def tool_get_dataset_info(server_id: str, dataset_id: int) -> str:
        """Gets detailed information for a specific dataset by ID."""
        return await datasets.get_dataset_info(manager, server_id, dataset_id)

    @mcp.tool(name="create_virtual_dataset")
    async def tool_create_virtual_dataset(server_id: str, dataset_name: str, database_id: int, sql: str, schema: Optional[str] = None, description: Optional[str] = None) -> str:
        """Save a SQL query as a virtual dataset for charting."""
        return await datasets.create_virtual_dataset(manager, server_id, dataset_name, database_id, sql, schema, description)

    @mcp.tool(name="superset_get_database_schema")
    async def tool_get_database_schema(server_id: str, database_id: int, schema_name: Optional[str] = None) -> str:
        """Retrieves schema (tables/columns) via information_schema SQL Lab queries."""
        return await datasets.get_database_schema(manager, server_id, database_id, schema_name)
