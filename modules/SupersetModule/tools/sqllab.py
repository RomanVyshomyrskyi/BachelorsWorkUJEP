import json
import httpx
from typing import Optional, Dict, Any
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request

async def sqllab_execute_query(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    sql_query: str,
    schema: Optional[str] = None,
    client_id: Optional[str] = None,
    tab_name: Optional[str] = None
) -> str:
    """
    Executes an SQL query through Superset's SQL Lab API.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."
    
    try:
        sqllab_payload: Dict[str, Any] = {
            "database_id": database_id,
            "sql": sql_query,
        }
        if schema:
            sqllab_payload["schema"] = schema
        if client_id:
            sqllab_payload["client_id"] = client_id
        if tab_name:
            sqllab_payload["tab_name"] = tab_name
        
        endpoint = "/api/v1/sqllab/execute/"
        resp = await execute_request(ctx, "POST", endpoint, json=sqllab_payload)
        resp.raise_for_status()
        
        return json.dumps(resp.json(), indent=2)
    except httpx.HTTPStatusError as e:
        return f"Error executing SQL Lab query: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return f"An unexpected error occurred while executing the SQL Lab query: {e}"

async def sqllab_get_query_results(
    manager: ConnectionManager,
    server_id: str,
    client_id: str
) -> str:
    """
    Retrieves the results of a previously executed SQL Lab query.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."
    
    try:
        endpoint = f"/api/v1/sqllab/results/{client_id}/"
        resp = await execute_request(ctx, "GET", endpoint)
        resp.raise_for_status()
        
        return json.dumps(resp.json(), indent=2)
    except httpx.HTTPStatusError as e:
        return f"Error retrieving SQL Lab query results: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return f"An unexpected error occurred while retrieving SQL Lab query results: {e}"
