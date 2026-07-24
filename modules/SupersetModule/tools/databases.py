"""
Database management tools for Apache Superset MCP integration.

Provides tools for listing and inspecting configured databases in Superset.
Databases are the data sources that datasets and charts are built upon.

MCP Tools Provided:
    - superset_list_databases: List all configured database connections
    - superset_get_database_info: Get details for a specific database
"""

import json
import httpx
from typing import Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.exceptions import DatabaseError


async def list_databases(manager: ConnectionManager, server_id: str) -> str:
    """
    MCP Tool: superset_list_databases - List all configured database connections.

    Fetches the list of all databases configured in Superset, including their
    names, engine types (postgres, mysql, mssql, etc.), and connection status.
    Useful for discovering available data sources before creating datasets or charts.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.

    Returns:
        JSON string containing the list of databases from GET /api/v1/database/,
        including each database's ID, name, engine, and connection metadata.
        Returns DatabaseError JSON if the server is not found.

    Example:
        result = await list_databases(manager, server_id="main")
        # Returns JSON array of all databases with their IDs, names, engines, and connection statuses
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return DatabaseError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        # Delegate to the generic API executor to fetch the database list
        return await impl_superset_api(manager, server_id, "GET", "/api/v1/database/")
    except Exception as e:
        return DatabaseError(f"Error listing databases: {e}", details=str(e)).to_json()


async def get_database_info(
    manager: ConnectionManager,
    server_id: str,
    database_id: int
) -> str:
    """
    MCP Tool: superset_get_database_info - Get details for a specific database.

    Fetches detailed information about a specific database connection, including
    the database name, engine type, SQLAlchemy URI (partially masked),
    extra configuration, and test connection status.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        database_id: The numeric ID of the database to inspect.

    Returns:
        JSON string containing the database details from GET /api/v1/database/{id},
        including database_name, engine, SQLAlchemy URI, extra config, and
        whether it has been tested. Returns DatabaseError JSON if the server
        is not found or the database doesn't exist.

    Example:
        result = await get_database_info(manager, server_id="main", database_id=1)
        # Returns JSON with database name, engine type, connection URI, and test connection status
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return DatabaseError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        # Delegate to the generic API executor to fetch specific database details
        return await impl_superset_api(
            manager, server_id, "GET", f"/api/v1/database/{database_id}"
        )
    except Exception as e:
        return DatabaseError(f"Error getting database info: {e}", details=str(e)).to_json()
