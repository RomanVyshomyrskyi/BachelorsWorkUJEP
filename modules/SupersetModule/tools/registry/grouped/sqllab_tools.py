"""
SQL Lab tool registration helpers.

Contains the tool registration functions for Superset SQL Lab operations:
- superset_sqllab_execute_query
- superset_sqllab_get_query_results
- execute_sql
- save_sql_query
- open_sql_lab_with_context
"""
from typing import Optional
from fastmcp import FastMCP

from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools import sqllab


def register_sqllab_tools(mcp: FastMCP, manager: ConnectionManager) -> None:
    """Register all SQL Lab tools with the FastMCP instance.

    Args:
        mcp: The FastMCP instance to register tools with.
        manager: The initialized ConnectionManager instance.
    """

    @mcp.tool(name="superset_sqllab_execute_query")
    async def tool_sqllab_execute_query(server_id: str, database_id: int, sql_query: str, schema: Optional[str] = None, client_id: Optional[str] = None, tab_name: Optional[str] = None) -> str:
        """Executes an SQL query through Superset's SQL Lab API."""
        return await sqllab.sqllab_execute_query(manager, server_id, database_id, sql_query, schema, client_id, tab_name)

    @mcp.tool(name="superset_sqllab_get_query_results")
    async def tool_sqllab_get_query_results(server_id: str, client_id: str) -> str:
        """Retrieves the results of a previously executed SQL Lab query."""
        return await sqllab.sqllab_get_query_results(manager, server_id, client_id)

    @mcp.tool(name="execute_sql")
    async def tool_execute_sql(server_id: str, database_id: int, sql_query: str, schema: Optional[str] = None) -> str:
        """Execute SQL queries and get results."""
        return await sqllab.sqllab_execute_query(manager, server_id, database_id, sql_query, schema)

    @mcp.tool(name="save_sql_query")
    async def tool_save_sql_query(server_id: str, database_id: int, label: str, sql: str, schema: Optional[str] = None, description: Optional[str] = None) -> str:
        """Save a SQL query to Saved Queries list."""
        return await sqllab.save_sql_query(manager, server_id, database_id, label, sql, schema, description)

    @mcp.tool(name="open_sql_lab_with_context")
    async def tool_open_sql_lab_with_context(server_id: str, database_id: int, sql: Optional[str] = None, schema: Optional[str] = None) -> str:
        """Generate SQL Lab URL with pre-filled sql."""
        return await sqllab.open_sql_lab_with_context(manager, server_id, database_id, sql, schema)
