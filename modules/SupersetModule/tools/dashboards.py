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
    Generates a basic, valid position_json structure for a Superset dashboard,
    arranging a list of charts in a simple layout.
    
    Follows ROOT -> GRID -> ROW -> CHART hierarchy as required by Superset.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."

    if not chart_ids:
        return "Error: At least one chart ID must be provided."

    # Build chart info list with names
    chart_info = []
    for chart_id in chart_ids:
        chart_details_str = await impl_get_resource(manager, server_id, "chart", chart_id)
        try:
            chart_details = json.loads(chart_details_str)
            slice_name = chart_details.get("result", {}).get("slice_name", f"Chart {chart_id}")
        except (json.JSONDecodeError, AttributeError):
            logger.warning(f"Could not fetch slice_name for chart {chart_id}. Using default name.")
            slice_name = f"Chart {chart_id}"
        chart_info.append({"id": chart_id, "name": slice_name})

    layout = _build_simple_layout(chart_info, layout_type, chart_width, chart_height)
    return json.dumps(layout, indent=2)


def _build_simple_layout(
    chart_info: List[Dict[str, Any]],
    layout_type: str = "row_of_charts",
    chart_width: int = 6,
    chart_height: int = 50
) -> Dict[str, Any]:
    """
    Builds position_json with ROOT -> GRID -> ROW -> CHART hierarchy.
    
    Groups charts into rows (max 2 charts per row for clear visibility)
    and assigns proper X/Y positions based on layout type.
    """
    layout = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {
            "type": "ROOT",
            "id": "ROOT_ID",
            "children": ["GRID_ID"]
        },
        "GRID_ID": {
            "type": "GRID",
            "id": "GRID_ID",
            "children": [],
            "parents": ["ROOT_ID"]
        }
    }

    # Group charts into rows (max 2 charts per row)
    rows = [chart_info[i:i + 2] for i in range(0, len(chart_info), 2)]
    
    for row_idx, row_charts in enumerate(rows):
        row_id = f"ROW-R{row_idx}"
        layout["GRID_ID"]["children"].append(row_id)
        
        layout[row_id] = {
            "type": "ROW",
            "id": row_id,
            "children": [],
            "parents": ["GRID_ID"],
            "meta": {"background": "BACKGROUND_TRANSPARENT"}
        }
        
        for chart_idx, chart in enumerate(row_charts):
            chart_element_id = f"CHART_{chart['id']}"
            
            # Calculate position within the row
            if layout_type == "row_of_charts":
                current_x = chart_idx * chart_width
                current_y = 0
            else:  # column_of_charts
                current_x = 0
                current_y = chart_idx * chart_height
            
            chart_meta = {
                "chartId": chart['id'],
                "width": chart_width,
                "height": chart_height,
                "startX": current_x,
                "startY": current_y,
                "sliceName": chart['name']
            }
            
            layout[chart_element_id] = {
                "type": "CHART",
                "id": chart_element_id,
                "children": [],
                "parents": [row_id],
                "meta": chart_meta
            }
            layout[row_id]["children"].append(chart_element_id)
    
    return layout

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
