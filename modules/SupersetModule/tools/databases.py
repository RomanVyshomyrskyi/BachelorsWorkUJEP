import json
import httpx
from typing import Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.exceptions import DatabaseError


async def list_databases(manager: ConnectionManager, server_id: str) -> str:
    ctx = manager.get_context(server_id)
    if not ctx:
        return DatabaseError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        return await impl_superset_api(manager, server_id, "GET", "/api/v1/database/")
    except Exception as e:
        return DatabaseError(f"Error listing databases: {e}", details=str(e)).to_json()


async def get_database_info(
    manager: ConnectionManager,
    server_id: str,
    database_id: int
) -> str:
    ctx = manager.get_context(server_id)
    if not ctx:
        return DatabaseError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        return await impl_superset_api(
            manager, server_id, "GET", f"/api/v1/database/{database_id}"
        )
    except Exception as e:
        return DatabaseError(f"Error getting database info: {e}", details=str(e)).to_json()
