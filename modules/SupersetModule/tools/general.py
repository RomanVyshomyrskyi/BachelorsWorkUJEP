import json
from typing import Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request, ensure_auth

async def impl_superset_api(
    manager: ConnectionManager,
    server_id: str,
    method: str,
    endpoint: str,
    json_body: Optional[str] = None,
    params: Optional[str] = None
) -> str:
    if method.upper() == "DELETE":
        return "Error: DELETE method is forbidden for safety reasons. 'YOLO mode' is not supported."

    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."

    try:
        await ensure_auth(ctx)
        
        data = json.loads(json_body) if json_body else None
        query_params = json.loads(params) if params else None
        
        # Ensure endpoint starts with slash
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint

        resp = await execute_request(
            ctx,
            method=method.upper(),
            endpoint=endpoint,
            json=data,
            params=query_params
        )
        
        # Try to format JSON output
        try:
            return json.dumps(resp.json(), indent=2)
        except:
            return f"Status: {resp.status_code}\nBody: {resp.text}"

    except Exception as e:
        return f"Error executing request: {e}"

async def superset_api_request(
    manager: ConnectionManager,
    server_id: str,
    method: str,
    endpoint: str,
    json_body: Optional[str] = None,
    params: Optional[str] = None
) -> str:
    """
    Executes a raw API request.
    """
    return await impl_superset_api(manager, server_id, method, endpoint, json_body, params)
