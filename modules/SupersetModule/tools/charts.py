import json
import httpx
from typing import Optional, Union
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule import rules
from modules.SupersetModule.superset_validation import (
    validate_chart_params,
    auto_fix_chart_params,
    format_error_summary,
)

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
    Validates and auto-fixes chart params before sending to API.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."
    
    try:
        # Parse params JSON
        params_dict = json.loads(params) if params else {}
        
        # Auto-fix common mistakes
        fixed_params = auto_fix_chart_params(viz_type, params_dict)
        
        # Validate remaining issues
        errors = validate_chart_params(viz_type, fixed_params)
        
        # Build warning if there are remaining errors
        warning = None
        if errors:
            warning = format_error_summary(errors)
        
        # Build chart payload with fixed params
        chart_payload = {
            "slice_name": slice_name,
            "description": description,
            "viz_type": viz_type,
            "datasource_id": datasource_id,
            "datasource_type": datasource_type,
            "params": json.dumps(fixed_params),
        }
        
        endpoint = "/api/v1/chart/"
        resp = await execute_request(ctx, "POST", endpoint, json=chart_payload)
        resp.raise_for_status()
        result = resp.json()
        
        # Append validation info to result
        if warning:
            result["_validation_warning"] = warning
        
        return json.dumps(result, indent=2)
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


async def list_charts(manager: ConnectionManager, server_id: str) -> str:
    """Lists all charts on a Superset server.
    
    Wrapper around GET /api/v1/chart/.
    
    Args:
        server_id: The ID of the configured Superset server.
    Returns:
        JSON string containing the list of charts.
    """
    return await impl_superset_api(manager, server_id, "GET", "/api/v1/chart/")


async def get_chart_info(
    manager: ConnectionManager,
    server_id: str,
    chart_id: Union[int, str]
) -> str:
    """Gets detailed information for a specific chart.
    
    Args:
        server_id: The ID of the configured Superset server.
        chart_id: The ID of the chart to retrieve.
    Returns:
        JSON string containing the chart details.
    """
    return await impl_superset_api(
        manager, server_id, "GET", f"/api/v1/chart/{chart_id}"
    )
