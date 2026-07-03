import json
import logging
import httpx
from typing import List, Dict, Any, Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.tools.resources import impl_get_resource
from modules.SupersetModule.tools.transfer import impl_transfer_item, transfer_dashboard as new_transfer_dashboard
from modules.SupersetModule import rules

logger = logging.getLogger(__name__)

async def generate_simple_dashboard_layout(
    manager: ConnectionManager,
    server_id: str,
    chart_ids: List[int],
    layout_type: str = "row_of_charts",
    chart_width: int = 6,
    chart_height: int = 50
) -> str:
    """
    Generates a basic, valid position_json structure for a Superset dashboard.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."

    if not chart_ids:
        return "Error: At least one chart ID must be provided."

    # Initialize the basic dashboard structure
    dashboard_json_map: Dict[str, Any] = {
        "DASHBOARD_VERSION": "2.0",
        "ROOT_ID": "ROOT_ID",
        "ROOT_ID-content": ["GRID_ID"],
        "GRID_ID": {
            "type": "GRID",
            "id": "GRID_ID",
            "children": [],
            "parents": ["ROOT_ID"]
        }
    }

    current_x = 0
    current_y = 0

    for i, chart_id in enumerate(chart_ids):
        chart_element_id = f"CHART_{chart_id}"
        
        # Fetch chart details to get sliceName
        chart_details_str = await impl_get_resource(manager, server_id, "chart", chart_id)
        try:
            chart_details = json.loads(chart_details_str)
            slice_name = chart_details.get("result", {}).get("slice_name", f"Chart {chart_id}")
        except (json.JSONDecodeError, AttributeError):
            logger.warning(f"Could not fetch slice_name for chart {chart_id}. Using default name.")
            slice_name = f"Chart {chart_id}"

        chart_meta = {
            "id": chart_id,
            "type": "CHART",
            "chartId": chart_id,
            "width": chart_width,
            "height": chart_height,
            "startX": current_x,
            "startY": current_y,
            "sliceName": slice_name
        }
        
        dashboard_json_map[chart_element_id] = {
            "type": "CHART",
            "id": chart_id,
            "children": [],
            "meta": chart_meta,
            "parents": ["GRID_ID"]
        }
        dashboard_json_map["GRID_ID"]["children"].append(chart_element_id)

        if layout_type == "row_of_charts":
            current_x += chart_width
            if current_x >= 12: # Wrap to next row
                current_x = 0
                current_y += chart_height
        elif layout_type == "column_of_charts":
            current_y += chart_height
            
    return json.dumps(dashboard_json_map, indent=2)

async def create_dashboard(
    manager: ConnectionManager,
    server_id: str,
    dashboard_title: str,
    position_json: str,
    slug: Optional[str] = None,
    json_metadata: Optional[str] = None,
    owners: Optional[List[int]] = None,
    roles: Optional[List[int]] = None,
    published: Optional[bool] = False
) -> str:
    """
    Creates a new dashboard on a Superset server.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."
    
    try:
        dashboard_payload = {
            "dashboard_title": dashboard_title,
            "position_json": position_json,
            "slug": slug,
            "json_metadata": json_metadata,
            "owners": owners if owners is not None else [],
            "roles": roles if roles is not None else [],
            "published": published
        }
        
        # Remove None values
        dashboard_payload = {k: v for k, v in dashboard_payload.items() if v is not None}

        endpoint = "/api/v1/dashboard/"
        resp = await execute_request(ctx, "POST", endpoint, json=dashboard_payload)
        resp.raise_for_status()
        
        return json.dumps(resp.json(), indent=2)
    except httpx.HTTPStatusError as e:
        return f"Error creating dashboard: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return f"An unexpected error occurred while creating the dashboard: {e}"

async def get_dashboard_api_info(manager: ConnectionManager, server_id: str) -> str:
    return await impl_superset_api(manager, server_id, "GET", "/api/v1/dashboard/_info")

async def update_dashboard(
    manager: ConnectionManager,
    server_id: str,
    dashboard_id: int,
    json_body: str
) -> str:
    return await impl_superset_api(manager, server_id, "PUT", f"/api/v1/dashboard/{dashboard_id}", json_body=json_body)

async def bulk_link_charts(
    manager: ConnectionManager,
    server_id: str,
    dashboard_id: int,
    chart_ids: List[int]
) -> str:
    """
    Links multiple charts to a dashboard in bulk.
    """
    results = []
    for cid in chart_ids:
        payload = json.dumps({"dashboards": [dashboard_id]})
        res = await impl_superset_api(manager, server_id, "PUT", f"/api/v1/chart/{cid}", json_body=payload)
        results.append(f"Chart {cid}: {res}")
    
    return "\n".join(results)

async def generate_robust_layout(
    manager: ConnectionManager,
    server_id: str,
    chart_ids: List[int]
) -> str:
    """
    Generates a robust, nested position_json for Superset dashboards.
    """
    chart_info = []
    for cid in chart_ids:
        res = await impl_get_resource(manager, server_id, "chart", cid)
        try:
            data = json.loads(res)
            chart_info.append({"id": cid, "name": data.get("result", {}).get("slice_name", f"Chart {cid}")})
        except:
            chart_info.append({"id": cid, "name": f"Chart {cid}"})
    
    layout = rules.generate_robust_dashboard_layout(chart_info)
    return json.dumps(layout, indent=2)

def get_dashboard_creation_rules() -> str:
    return rules.get_dashboard_creation_rules()

async def transfer_dashboard(
    manager: ConnectionManager,
    source_server_id: str,
    target_server_id: str,
    dashboard_id: int,
    db_mappings: Optional[str] = None,
    table_mappings: Optional[str] = None
) -> str:
    return await new_transfer_dashboard(manager, source_server_id, target_server_id, dashboard_id, db_mappings, table_mappings)
