"""Layout generation functions for Superset dashboards.

Provides functions to generate simple and robust position JSON layouts
with ROOT -> GRID -> ROW -> CHART hierarchy.
"""
import json
import uuid
from typing import Dict, Any, List

from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.tools.resources import impl_get_resource
from modules.SupersetModule.exceptions import DashboardError
from modules.SupersetModule import rules
from modules.log_utils import LogCollector

log = LogCollector(__name__)


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
    Uses consistent UUID format: CHART-{uuid}-{chartId} and ROW-R{idx}-{uuid}
    matching working Superset dashboard format.

    Args:
        chart_info: List of dicts with 'id' and 'name' keys for each chart.
        layout_type: 'row_of_charts' or 'column_of_charts'. Defaults to "row_of_charts".
        chart_width: Width of each chart cell in grid units. Defaults to 6.
        chart_height: Height of each chart cell in pixels. Defaults to 50.

    Returns:
        Dict representing a valid Superset position_json dashboard layout.
    """
    dashboard_uuid = str(uuid.uuid4())[:8]

    # Step 1: Create the base layout skeleton (v2 format with ROOT + GRID)
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

    # Step 2: Group charts into rows (max 2 charts per row)
    rows = [chart_info[i:i + 2] for i in range(0, len(chart_info), 2)]

    for row_idx, row_charts in enumerate(rows):
        row_id = f"ROW-R{row_idx}-{dashboard_uuid}"
        layout["GRID_ID"]["children"].append(row_id)

        # Step 3: Create ROW component in the layout
        layout[row_id] = {
            "type": "ROW",
            "id": row_id,
            "children": [],
            "parents": ["GRID_ID"],
            "meta": {"background": "BACKGROUND_TRANSPARENT"}
        }

        for chart_idx, chart in enumerate(row_charts):
            chart_element_id = f"CHART-{dashboard_uuid}-{chart['id']}"

            # Step 4: Calculate position within the row based on layout type
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


async def generate_simple_dashboard_layout(
    manager: ConnectionManager,
    server_id: str,
    chart_ids: List[int],
    layout_type: str = "row_of_charts",
    chart_width: int = 6,
    chart_height: int = 50
) -> str:
    """
    MCP Tool: superset_generate_simple_dashboard_layout - Generate a simple row/column layout.

    Creates a position JSON with ROOT -> GRID -> ROW -> CHART hierarchy. Max 2 charts
    per row for clear visibility. Uses consistent UUID-based IDs matching the Superset
    dashboard v2 format.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_ids: List of chart IDs to include in the layout.
        layout_type: 'row_of_charts' (horizontal) or 'column_of_charts' (vertical). Defaults to "row_of_charts".
        chart_width: Width of each chart cell in grid units. Defaults to 6.
        chart_height: Height of each chart cell in pixels. Defaults to 50.

    Returns:
        JSON string of the position_json layout object.

    Example:
        result = await generate_simple_dashboard_layout(
            manager, "default", chart_ids=[123, 456],
            layout_type="row_of_charts", chart_width=6, chart_height=50
        )
        # Returns JSON position layout with ROOT -> GRID -> ROW -> CHART hierarchy.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return log.collect(DashboardError(f"Server '{server_id}' not found.", status_code=404).to_json())

    if not chart_ids:
        return log.collect(DashboardError("At least one chart ID must be provided.").to_json())

    chart_info = []
    for chart_id in chart_ids:
        chart_details_str = await impl_get_resource(manager, server_id, "chart", chart_id)
        try:
            chart_details = json.loads(chart_details_str)
            slice_name = chart_details.get("result", {}).get("slice_name", f"Chart {chart_id}")
        except (json.JSONDecodeError, AttributeError):
            log.warning(f"Could not fetch slice_name for chart {chart_id}. Using default name.")
            slice_name = f"Chart {chart_id}"
        chart_info.append({"id": chart_id, "name": slice_name})

    layout = _build_simple_layout(chart_info, layout_type, chart_width, chart_height)
    return log.collect(json.dumps(layout, indent=2))


async def generate_robust_layout(
    manager: ConnectionManager,
    server_id: str,
    chart_ids: List[int]
) -> str:
    """
    MCP Tool: superset_generate_robust_dashboard_layout - Generate a robust nested layout.

    Creates a nested position_json with auto-sizing for each chart based on its
    viz_type. Uses ROOT -> GRID -> ROW -> [TABS -> ] CHART hierarchy. Appropriate
    for complex dashboards with many charts and mixed chart types.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_ids: List of chart IDs to include. Order determines layout position.

    Returns:
        JSON string of the position_json layout, or DashboardError if server not found.

    Example:
        result = await generate_robust_layout(manager, "default", chart_ids=[123, 456])
        # Returns JSON nested position layout with auto-sizing per viz_type.
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
    return log.collect(json.dumps(layout, indent=2))
