import json
import httpx
from typing import Optional, Union, Dict, Any
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


async def generate_chart(
    manager: ConnectionManager,
    server_id: str,
    dataset_id: int,
    config: str,
    slice_name: Optional[str] = None,
    save_chart: bool = True,
    description: Optional[str] = None
) -> str:
    """Create and optionally save a new chart.
    
    This is the official Apache MCP tool name. Use generate_explore_link
    for exploration (no permanent chart created). Use generate_chart with
    save_chart=True only when the user wants to save permanently.
    
    Args:
        server_id: The ID of the configured Superset server.
        dataset_id: The ID of the dataset to base the chart on.
        config: JSON string of chart configuration (viz_type, metrics, etc.).
        slice_name: Optional name for the chart. Defaults to "Chart from dataset {dataset_id}".
        save_chart: If True, saves the chart permanently. If False, returns preview only.
        description: Optional description.
    Returns:
        JSON string containing the chart result.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."
    
    try:
        # Parse config
        chart_config = json.loads(config) if config else {}
        
        # Build form_data
        form_data: Dict[str, Any] = {
            "datasource_id": dataset_id,
            "datasource_type": "table",
        }
        form_data.update(chart_config)
        
        if not save_chart:
            # Return explore-style URL without saving
            base_url = ctx.config.base_url.rstrip("/")
            explore_url = f"{base_url}/explore/?form_data={json.dumps(form_data)}"
            return json.dumps({
                "url": explore_url,
                "saved": False,
                "config": chart_config
            }, indent=2)
        
        # Build chart payload
        chart_name = slice_name or f"Chart from dataset {dataset_id}"
        
        chart_payload = {
            "slice_name": chart_name,
            "datasource_id": dataset_id,
            "datasource_type": "table",
            "viz_type": chart_config.get("viz_type", "table"),
            "params": json.dumps(form_data),
        }
        if description:
            chart_payload["description"] = description
        
        endpoint = "/api/v1/chart/"
        resp = await execute_request(ctx, "POST", endpoint, json=chart_payload)
        resp.raise_for_status()
        result = resp.json()
        
        return json.dumps({
            "saved": True,
            "chart_id": result.get("id"),
            "slice_name": chart_name,
            "url": f"{ctx.config.base_url.rstrip('/')}/chart/{result.get('id')}/",
            "result": result
        }, indent=2)
        
    except httpx.HTTPStatusError as e:
        return f"Error generating chart: {e.response.status_code} - {e.response.text}"
    except json.JSONDecodeError:
        return f"Error: 'config' is not a valid JSON string."
    except Exception as e:
        return f"An unexpected error occurred while generating the chart: {e}"


async def get_chart_preview(
    manager: ConnectionManager,
    server_id: str,
    chart_id: Union[int, str]
) -> str:
    """Get a visual preview of a chart with image URL.
    
    Returns a URL to a PNG preview image of the chart.
    
    Args:
        server_id: The ID of the configured Superset server.
        chart_id: The ID of the chart to preview.
    Returns:
        JSON string containing the preview URL.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."
    
    try:
        base_url = ctx.config.base_url.rstrip("/")
        preview_url = f"{base_url}/chart/{chart_id}/data/"
        
        return json.dumps({
            "preview_url": preview_url,
            "chart_id": chart_id,
            "note": "Use this URL to view the chart preview image."
        }, indent=2)
    except Exception as e:
        return f"An unexpected error occurred while getting chart preview: {e}"


async def get_chart_data(
    manager: ConnectionManager,
    server_id: str,
    chart_id: Union[int, str]
) -> str:
    """Get underlying chart data in text-friendly format.
    
    Returns the raw data that backs the chart, suitable for
    programmatic analysis or reporting.
    
    Args:
        server_id: The ID of the configured Superset server.
        chart_id: The ID of the chart.
    Returns:
        JSON string containing the chart data.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."
    
    try:
        endpoint = f"/api/v1/chart/{chart_id}/data/"
        resp = await execute_request(ctx, "GET", endpoint)
        resp.raise_for_status()
        
        return json.dumps(resp.json(), indent=2)
    except httpx.HTTPStatusError as e:
        return f"Error getting chart data: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return f"An unexpected error occurred while getting chart data: {e}"


async def get_chart_type_schema(
    manager: ConnectionManager,
    server_id: str,
    chart_type: str
) -> str:
    """Get schema for a specific chart type.
    
    Returns the expected parameters and configuration for a given
    visualization type, useful for generating correct chart configs.
    
    Args:
        server_id: The ID of the configured Superset server.
        chart_type: The visualization type (e.g., 'xy', 'big_number', 'table').
    Returns:
        JSON string containing the chart type schema.
    """
    return await impl_superset_api(
        manager, server_id, "GET", f"/api/v1/chart/schemas/{chart_type}/"
    )
