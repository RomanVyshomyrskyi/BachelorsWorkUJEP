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


async def save_sql_query(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    label: str,
    sql: str,
    schema: Optional[str] = None,
    description: Optional[str] = None
) -> str:
    """Save a SQL query to the Saved Queries list.
    
    Args:
        server_id: The ID of the configured Superset server.
        database_id: The ID of the database.
        label: The name/label for the saved query.
        sql: The SQL query text to save.
        schema: Optional schema name.
        description: Optional description for the saved query.
    Returns:
        JSON string containing the saved query details.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."
    
    try:
        payload: Dict[str, Any] = {
            "database_id": database_id,
            "label": label,
            "sql": sql,
        }
        if schema:
            payload["schema"] = schema
        if description:
            payload["description"] = description
        
        endpoint = "/api/v1/saved-query/"
        resp = await execute_request(ctx, "POST", endpoint, json=payload)
        resp.raise_for_status()
        
        return json.dumps(resp.json(), indent=2)
    except httpx.HTTPStatusError as e:
        return f"Error saving SQL query: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return f"An unexpected error occurred while saving the SQL query: {e}"


async def open_sql_lab_with_context(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    sql: Optional[str] = None,
    schema: Optional[str] = None
) -> str:
    """Generate a SQL Lab URL with pre-filled SQL query.
    
    Args:
        server_id: The ID of the configured Superset server.
        database_id: The ID of the database.
        sql: Optional pre-filled SQL query.
        schema: Optional schema name.
    Returns:
        JSON string containing the SQL Lab URL.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."
    
    try:
        base_url = ctx.config.base_url.rstrip("/")
        
        # Build query params
        params = f"dbId={database_id}"
        if sql:
            params += f"&qtSQL={sql}"
        if schema:
            params += f"&schema={schema}"
        
        sql_lab_url = f"{base_url}/sqllab/?{params}"
        
        return json.dumps({
            "url": sql_lab_url,
            "database_id": database_id,
            "sql": sql,
            "schema": schema
        }, indent=2)
    except Exception as e:
        return f"An unexpected error occurred while generating SQL Lab URL: {e}"
