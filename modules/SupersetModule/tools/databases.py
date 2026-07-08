import json
from typing import Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.general import impl_superset_api


async def list_databases(manager: ConnectionManager, server_id: str) -> str:
    """Lists all database connections on a Superset server.
    
    Wrapper around GET /api/v1/database/.
    
    Args:
        server_id: The ID of the configured Superset server.
    Returns:
        JSON string containing the list of databases.
    """
    return await impl_superset_api(manager, server_id, "GET", "/api/v1/database/")


async def get_database_info(
    manager: ConnectionManager,
    server_id: str,
    database_id: int
) -> str:
    """Gets detailed information for a specific database connection.
    
    Args:
        server_id: The ID of the configured Superset server.
        database_id: The ID of the database to retrieve.
    Returns:
        JSON string containing the database details.
    """
    return await impl_superset_api(
        manager, server_id, "GET", f"/api/v1/database/{database_id}"
    )
