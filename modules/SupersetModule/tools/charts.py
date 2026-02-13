import json
import httpx
from typing import Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule import rules

async def get_chart_api_info(manager: ConnectionManager, server_id: str) -> str:
    """
    Retrieves metadata about the chart API.
    """
    return await impl_superset_api(manager, server_id, "GET", "/api/v1/chart/_info")

async def create_chart(
    manager: ConnectionManager,
    server_id: str,
    slice_name: str,
    viz_type: str,
    datasource_id: int,
    datasource_type: str,
    params: str, # JSON string
    description: Optional[str] = None
) -> str:
    """
    Creates a new chart (slice) on a Superset server.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."
    
    try:
        chart_payload = {
            "slice_name": slice_name,
            "description": description,
            "viz_type": viz_type,
            "datasource_id": datasource_id,
            "datasource_type": datasource_type,
            "params": params,
        }
        
        endpoint = "/api/v1/chart/"
        resp = await execute_request(ctx, "POST", endpoint, json=chart_payload)
        resp.raise_for_status()
        
        return json.dumps(resp.json(), indent=2)
    except httpx.HTTPStatusError as e:
        return f"Error creating chart: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return f"An unexpected error occurred while creating the chart: {e}"

async def update_chart(
    manager: ConnectionManager,
    server_id: str,
    chart_id: int,
    json_body: str
) -> str:
    """
    Updates an existing chart.
    """
    return await impl_superset_api(manager, server_id, "PUT", f"/api/v1/chart/{chart_id}", json_body=json_body)

def get_standard_chart_params(viz_type: str, datasource_id: int, overrides_json: Optional[str] = None) -> str:
    """
    Returns a JSON string of standard parameters for a given visualization type.
    """
    overrides = json.loads(overrides_json) if overrides_json else {}
    params = rules.get_standard_chart_params(viz_type, datasource_id, **overrides)
    return json.dumps(params, indent=2)

def get_chart_creation_rules() -> str:
    """Returns the expert rules for creating functional Superset charts."""
    return rules.get_chart_creation_rules()
