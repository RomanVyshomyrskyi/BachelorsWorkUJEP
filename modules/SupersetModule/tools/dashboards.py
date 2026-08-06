import json
import httpx
import time
import logging
from typing import List, Dict, Any, Optional, Union

logger = logging.getLogger(__name__)
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.tools.resources import impl_get_resource
from modules.SupersetModule.tools.transfer import impl_transfer_item, transfer_dashboard as new_transfer_dashboard
from modules.SupersetModule.exceptions import DashboardError
from modules.SupersetModule.schemas.dashboard import (
     DashboardListItem,
     DashboardDetail,
     DashboardGenerateResponse,
     ChartLinkResult,
 )
from modules.SupersetModule import rules
from modules.SupersetModule.superset_mermaid import dashboard_to_mermaid
from modules.log_utils import LogCollector
from modules.metrics import get_metrics
from modules.SupersetModule.tools.chart_validation import validate_chart_data_against_dataset, format_validation_error

log = LogCollector(__name__)

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
    # Step 1: Validate server context exists
    ctx = manager.get_context(server_id)
    if not ctx:
        return log.collect(DashboardError(f"Server '{server_id}' not found.", status_code=404).to_json())

    # Step 2: Validate chart_ids is not empty
    if not chart_ids:
        return log.collect(DashboardError("At least one chart ID must be provided.").to_json())

    # Step 3: Fetch chart names from Superset for descriptive row labels
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

    # Step 4: Build the layout using the private helper
    layout = _build_simple_layout(chart_info, layout_type, chart_width, chart_height)
    return log.collect(json.dumps(layout, indent=2))


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
    import uuid
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


async def get_dashboard_info(
    manager: ConnectionManager,
    server_id: str,
    dashboard_id: Union[int, str]
) -> str:
    """Gets detailed information for a specific dashboard.
    
    Args:
        server_id: The ID of the configured Superset server.
        dashboard_id: The ID of the dashboard to retrieve.
    Returns:
        JSON string containing the dashboard details.

    Example:
        result = await get_dashboard_info(manager, "default", dashboard_id=789)
        # Returns JSON with dashboard title, position_json, charts, and metadata.
    """
    return await impl_superset_api(
        manager, server_id, "GET", f"/api/v1/dashboard/{dashboard_id}"
    )


async def create_dashboard(
     manager: ConnectionManager,
     server_id: str,
     dashboard_title: str,
     position_json: str,
     slug: Optional[str] = None,
     json_metadata: Optional[str] = None,
     owners: Optional[List[int]] = None,
     roles: Optional[List[int]] = None,
     published: Optional[bool] = False,
     skip_chart_validation: bool = False
 ) -> str:
     """
     MCP Tool: superset_create_dashboard - Create a dashboard with custom position JSON.

     Creates a new Superset dashboard from a pre-built position_json layout.
     Performs three levels of pre-flight validation: structure validation of the
     position JSON, existence check of all chart IDs, and data endpoint testing
     for each chart to ensure they render properly.

     Args:
         manager: The ConnectionManager instance with Superset connection details.
         server_id: The ID of the configured Superset server.
         dashboard_title: The display title for the dashboard in Superset.
         position_json: JSON string defining the dashboard layout.
         slug: Optional URL-friendly identifier for the dashboard.
         json_metadata: Optional JSON string of additional metadata.
         owners: Optional list of user IDs who own the dashboard.
         roles: Optional list of role IDs that have access to the dashboard.
         published: Whether the dashboard is published (visible) or saved as draft. Defaults to False.
         skip_chart_validation: If True, skip the pre-flight chart data endpoint validation.
             Useful when charts were already validated externally (e.g., during transfer). Defaults to False.

     Returns:
         JSON string containing the created dashboard's details on success,
            or a DashboardError JSON with specific validation errors on failure.

    Example:
        result = await create_dashboard(
            manager, "default",
            dashboard_title="Sales Dashboard",
            position_json='{"DASHBOARD_VERSION_KEY": "v2", "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]}}',
            published=True
        )
        # Returns JSON with created dashboard details, ID, and Mermaid graph.
    """
     # Step 1: Validate server context exists
     ctx = manager.get_context(server_id)
     if not ctx:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_create_dashboard", status="error").inc()
         mc.record_error(tool="superset_create_dashboard", error_message=f"Server '{server_id}' not found.")
         return log.collect(DashboardError(f"Server '{server_id}' not found.", status_code=404).to_json())

     # Step 2: Extract chart IDs from position JSON for validation
     chart_ids = _extract_chart_ids_from_position_json(position_json)

     # Step 3: Validate position JSON structure
     structure_errors = _validate_position_json_structure(position_json)
     if structure_errors:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_create_dashboard", status="error").inc()
         mc.record_error(
             tool="superset_create_dashboard",
             error_message=f"Dashboard creation blocked: {len(structure_errors)} structure errors"
         )
         return log.collect(DashboardError(
             "Dashboard creation blocked: Invalid position JSON structure",
             details=(
                 f"Dashboard '{dashboard_title}' cannot be created — position JSON has "
                 f"{len(structure_errors)} structural issue(s):\n\n"
                 + "\n".join(f"  {i+1}. {e}" for i, e in enumerate(structure_errors))
             ),
             status_code=400,
         ).to_json())

     # Step 4: Validate all chart IDs exist
     if chart_ids:
         invalid_charts = await _validate_charts_exist(manager, server_id, chart_ids)
         if invalid_charts:
             mc = get_metrics()
             mc.tool_calls.labels(tool="superset_create_dashboard", status="error").inc()
             mc.record_error(
                 tool="superset_create_dashboard",
                 error_message=f"Dashboard creation blocked: {len(invalid_charts)} charts not found"
             )
             return log.collect(DashboardError(
                 "Dashboard creation blocked: Chart validation failed",
                 details=(
                     f"Dashboard '{dashboard_title}' cannot be created — one or more chart IDs "
                     f"in position JSON do not exist on the server:\n\n"
                     + "\n".join(f"  {i+1}. Chart ID {cid} not found" for i, cid in enumerate(invalid_charts))
                     + f"\n\nValidated chart IDs: {chart_ids}"
                 ),
                 status_code=400,
             ).to_json())

         # Step 5: Pre-flight — test all charts' data endpoints
         if not skip_chart_validation:
             logger.info(f"Running pre-flight chart data validation for dashboard '{dashboard_title}'")
             failed_charts = await _pre_validate_chart_data(manager, server_id, chart_ids)
             
             if failed_charts:
                 mc = get_metrics()
                 mc.tool_calls.labels(tool="superset_create_dashboard", status="error").inc()
                 mc.record_error(
                     tool="superset_create_dashboard",
                     error_message=f"Dashboard creation blocked: {len(failed_charts)} charts fail data endpoint"
                 )
                 
                 failed_details = "\n".join(
                     f"  {i+1}. Chart {fc['chart_id']} ({fc['viz_type']}, '{fc['slice_name']}'): {fc['error']}"
                     for i, fc in enumerate(failed_charts)
                 )
                 return log.collect(DashboardError(
                     "Dashboard creation blocked: Chart data validation failed",
                     details=(
                         f"Dashboard '{dashboard_title}' cannot be created — one or more charts "
                         f"fail to render:\n\n"
                         + failed_details
                         + "\n\n"
                         + "Fix the failing charts before creating the dashboard."
                     ),
                     status_code=400,
             ).to_json())
     elif not chart_ids:
         logger.warning(
             f"No chart IDs extracted from position JSON for dashboard '{dashboard_title}'. "
             f"The dashboard will be created with no linked charts."
         )

     start_time = time.monotonic()
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
         dashboard_payload = {k: v for k, v in dashboard_payload.items() if v is not None}

         endpoint = "/api/v1/dashboard/"
         resp = await execute_request(ctx, "POST", endpoint, json=dashboard_payload)
         resp.raise_for_status()
         result = resp.json()

         try:
             result["_mermaid_graph"] = dashboard_to_mermaid(
                 dashboard_title,
                 chart_ids=[],
                 chart_info=result.get("charts", []),
             )
         except Exception:
             result["_mermaid_graph"] = None

         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_create_dashboard", status="success").inc()
         mc.tool_duration.labels(tool="superset_create_dashboard").observe(time.monotonic() - start_time)
         mc.resources_created.labels(resource_type="dashboard").inc()
         return log.collect(json.dumps(result, indent=2))
     except httpx.HTTPStatusError as e:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_create_dashboard", status="error").inc()
         mc.record_error(tool="superset_create_dashboard", error_message=f"HTTP {e.response.status_code} creating dashboard", status_code=e.response.status_code)
         return log.collect(DashboardError(
             f"HTTP {e.response.status_code} creating dashboard",
             status_code=e.response.status_code,
             details=e.response.text,
         ).to_json())
     except Exception as e:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_create_dashboard", status="error").inc()
         mc.record_error(tool="superset_create_dashboard", error_message=str(e))
         return log.collect(DashboardError(f"Unexpected error creating dashboard: {e}", details=str(e)).to_json())

async def get_dashboard_api_info(manager: ConnectionManager, server_id: str) -> str:
    """
    MCP Tool: superset_get_dashboard_api_info - Get metadata about the dashboard API.

    Fetches the dashboard API's _info endpoint which contains metadata about
    supported features, available filters, permissions, and API properties.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server to query.

    Returns:
        JSON string containing the dashboard API metadata from /api/v1/dashboard/_info.

    Example:
        result = await get_dashboard_api_info(manager, "default")
        # Returns JSON with dashboard API metadata including supported features and filters.
    """
    # Delegate to the generic Superset API helper for the GET request
    return await impl_superset_api(manager, server_id, "GET", "/api/v1/dashboard/_info")

async def update_dashboard(
    manager: ConnectionManager,
    server_id: str,
    dashboard_id: int,
    json_body: str
) -> str:
    """
    MCP Tool: superset_update_dashboard - Update an existing dashboard's configuration.

    Sends a PUT request to the Superset dashboard API to modify a dashboard's
    settings such as title, position_json, slug, metadata, or ownership.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        dashboard_id: The numeric ID of the dashboard to update.
        json_body: JSON string containing the fields to update.

    Returns:
        JSON string containing the updated dashboard's details from the API response,
            or an error JSON if the update fails.

    Example:
        result = await update_dashboard(
            manager, "default", dashboard_id=789,
            json_body='{"dashboard_title": "Updated Dashboard"}'
        )
        # Returns JSON with updated dashboard details.
    """
    return await impl_superset_api(manager, server_id, "PUT", f"/api/v1/dashboard/{dashboard_id}", json_body=json_body)

async def bulk_link_charts(
    manager: ConnectionManager,
    server_id: str,
    dashboard_id: int,
    chart_ids: List[int]
) -> str:
    """
    MCP Tool: superset_bulk_link_charts - Link multiple charts to a dashboard at once.

    Iterates over the provided chart IDs and updates each chart's dashboard
    association via PUT /api/v1/chart/{id}. Charts are linked to the target
    dashboard individually, and any failures are collected and reported.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        dashboard_id: The numeric ID of the dashboard to link charts to.
        chart_ids: List of chart IDs to link to the dashboard.

    Returns:
        String with per-chart status messages. Prefixed with "WARNING:" if any
            charts failed to link, otherwise a plain list of success messages.

    Example:
        result = await bulk_link_charts(
            manager, "default", dashboard_id=789, chart_ids=[123, 456]
        )
        # Returns string with per-chart link status messages.
    """
    results = []
    errors = []
    for cid in chart_ids:
        try:
            # Step 1: Build payload to associate chart with dashboard
            payload = json.dumps({"dashboards": [dashboard_id]})
            res = await impl_superset_api(manager, server_id, "PUT", f"/api/v1/chart/{cid}", json_body=payload)
            results.append(f"Chart {cid}: linked successfully")
        except Exception as e:
            error_msg = f"Chart {cid}: failed to link - {str(e)}"
            errors.append(error_msg)
            results.append(error_msg)

    if errors:
        return "WARNING: Some charts failed to link:\n" + "\n".join(errors)
    return "\n".join(results)

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

def get_dashboard_creation_rules() -> str:
    """
    MCP Tool: superset_get_dashboard_creation_rules - Get expert rules for creating dashboards.

    Returns a set of best practices and guidelines for building functional
    Superset dashboards. Includes layout recommendations, chart sizing tips,
    and common pitfalls to avoid.

    Returns:
        String containing the expert rules for dashboard creation.

    Example:
        result = get_dashboard_creation_rules()
        # Returns string with expert guidelines for dashboard creation.
    """
    return rules.get_dashboard_creation_rules()

async def transfer_dashboard(
    manager: ConnectionManager,
    source_server_id: str,
    target_server_id: str,
    dashboard_id: int,
    db_mappings: Optional[str] = None,
    table_mappings: Optional[str] = None
) -> str:
    """
    MCP Tool: superset_transfer_dashboard - Transfer a dashboard between servers.

    Copies a dashboard and all its linked charts from one Superset server to
    another. Optionally maps database IDs and table names between the source
    and target servers for cross-environment transfers.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        source_server_id: The ID of the source Superset server.
        target_server_id: The ID of the target Superset server.
        dashboard_id: The numeric ID of the dashboard to transfer.
        db_mappings: Optional JSON string of database ID mappings between servers.
        table_mappings: Optional JSON string of table name mappings between servers.

    Returns:
        JSON string with transfer results, including updated chart/dashboard IDs
            on the target server. Returns NEED_INPUT if manual mappings are required.

    Example:
        result = await transfer_dashboard(
            manager, source_server_id="source", target_server_id="target",
            dashboard_id=789, db_mappings='{"1": 2}', table_mappings='{"old": "new"}'
        )
        # Returns JSON with transfer results including updated chart/dashboard IDs.
    """
    return await new_transfer_dashboard(manager, source_server_id, target_server_id, dashboard_id, db_mappings, table_mappings)


async def generate_dashboard(
     manager: ConnectionManager,
     server_id: str,
     dashboard_title: str,
     chart_ids: List[int],
     slug: Optional[str] = None,
     json_metadata: Optional[str] = None,
     published: bool = False,
     layout_type: str = "robust"
 ) -> str:
     """
     MCP Tool: superset_generate_dashboard - Generate a new dashboard from chart IDs.

     Creates a new Superset dashboard by automatically generating a layout from
     the provided chart IDs. Validates that all charts exist before creation,
     generates the position JSON layout, creates the dashboard, and links
     all charts to it.

     Args:
         manager: The ConnectionManager instance with Superset connection details.
         server_id: The ID of the configured Superset server.
         dashboard_title: The display title for the dashboard in Superset.
         chart_ids: List of chart IDs to include in the dashboard.
         slug: Optional URL-friendly identifier for the dashboard.
         json_metadata: Optional JSON string of additional metadata.
         published: Whether the dashboard is published or saved as draft. Defaults to False.
         layout_type: 'robust' (nested hierarchy) or 'simple' (flat row/column). Defaults to "robust".

     Returns:
         JSON string containing the created dashboard's details on success,
            or a DashboardError JSON with validation errors on failure.

    Example:
        result = await generate_dashboard(
            manager, "default",
            dashboard_title="Sales Dashboard",
            chart_ids=[123, 456],
            layout_type="robust",
            published=True
        )
        # Returns JSON with created dashboard details, ID, and Mermaid graph.
    """
     # Step 1: Validate server context exists
     ctx = manager.get_context(server_id)
     if not ctx:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_generate_dashboard", status="error").inc()
         mc.record_error(tool="superset_generate_dashboard", error_message=f"Server '{server_id}' not found.")
         return log.collect(DashboardError(f"Server '{server_id}' not found.", status_code=404).to_json())

     # Step 2: Validate chart_ids is not empty
     if not chart_ids:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_generate_dashboard", status="error").inc()
         mc.record_error(tool="superset_generate_dashboard", error_message="At least one chart ID must be provided.")
         return log.collect(DashboardError("At least one chart ID must be provided.").to_json())

     # Step 3: Validate that all charts exist before creating dashboard
     invalid_charts = await _validate_charts_exist(manager, server_id, chart_ids)
     if invalid_charts:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_generate_dashboard", status="error").inc()
         mc.record_error(
             tool="superset_generate_dashboard",
             error_message=f"Dashboard generation blocked: {len(invalid_charts)} charts not found"
         )
         return log.collect(DashboardError(
             "Dashboard generation blocked: Chart validation failed",
             details=(
                 f"Dashboard '{dashboard_title}' cannot be created — one or more charts do not exist:\n\n"
                 + "\n".join(f"  - Chart {cid} not found" for cid in invalid_charts)
                 + f"\n\nAvailable chart IDs can be found with 'superset_list_charts'."
             ),
             status_code=400,
         ).to_json())

     # Step 3b: Validate column references in all charts against their datasets
     column_errors = []
     for chart_id in chart_ids:
         try:
             chart_raw = await impl_get_resource(manager, server_id, "chart", chart_id)
             chart_data = json.loads(chart_raw)
             chart_result = chart_data.get("result", {})
             chart_params = chart_result.get("params", {})
             datasource_id = chart_result.get("datasource_id")
             viz_type = chart_result.get("viz_type", "")
             slice_name = chart_result.get("slice_name", f"Chart {chart_id}")

             if not datasource_id:
                 continue

             if isinstance(chart_params, str):
                 try:
                     chart_params = json.loads(chart_params)
                 except (json.JSONDecodeError, TypeError):
                     chart_params = {}

             ds_raw = await impl_superset_api(
                 manager, server_id, "GET", f"/api/v1/dataset/{datasource_id}"
             )
             ds_data = json.loads(ds_raw)
             dataset_columns = ds_data.get("result", {}).get("columns", [])

             if not dataset_columns:
                 column_errors.append(
                     f"Chart {chart_id} ('{slice_name}'): dataset {datasource_id} has no columns defined"
                 )
                 continue

             validation = validate_chart_data_against_dataset(
                 chart_params, dataset_columns, viz_type
             )
             if not validation["is_valid"]:
                 missing = validation.get("missing_columns", [])
                 for mc_obj in missing:
                     col = mc_obj.get("requested", "?")
                     field = mc_obj.get("field", "?")
                     suggestions = mc_obj.get("suggestions", [])
                     sug = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
                     column_errors.append(
                         f"Chart {chart_id} ('{slice_name}'): column '{col}' "
                         f"({field}) not found in dataset.{sug}"
                     )
         except Exception as e:
             column_errors.append(f"Chart {chart_id}: failed to validate columns ({e})")

     if column_errors:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_generate_dashboard", status="error").inc()
         mc.record_error(
             tool="superset_generate_dashboard",
             error_message=f"Column validation failed for {len(column_errors)} chart(s)"
         )
         return log.collect(DashboardError(
             "Dashboard generation blocked: Column validation failed",
             details=(
                 f"Dashboard '{dashboard_title}' cannot be created — "
                 f"one or more charts reference columns that don't exist "
                 f"in their datasets:\n\n"
                 + "\n".join(f"  - {e}" for e in column_errors)
             ),
             status_code=400,
         ).to_json())

     start_time = time.monotonic()
     try:
         # Step 4: Generate position JSON layout based on the chosen layout type
         if layout_type == "simple":
             position_json = _build_simple_layout_json(chart_ids)
         else:
             position_json = _build_robust_layout_json(chart_ids)

         dashboard_payload = {
             "dashboard_title": dashboard_title,
             "position_json": position_json,
             "slug": slug,
             "json_metadata": json_metadata,
             "owners": [],
             "roles": [],
             "published": published
         }
         dashboard_payload = {k: v for k, v in dashboard_payload.items() if v is not None}

         # Step 5: Send POST request to create the dashboard
         endpoint = "/api/v1/dashboard/"
         resp = await execute_request(ctx, "POST", endpoint, json=dashboard_payload)
         resp.raise_for_status()
         result = resp.json()

         # Step 6: Link all chart IDs to the newly created dashboard
         await bulk_link_charts(manager, server_id, result.get("id"), chart_ids)

         try:
             result["_mermaid_graph"] = dashboard_to_mermaid(
                 dashboard_title,
                 chart_ids=chart_ids,
             )
         except Exception:
             result["_mermaid_graph"] = None

         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_generate_dashboard", status="success").inc()
         mc.tool_duration.labels(tool="superset_generate_dashboard").observe(time.monotonic() - start_time)
         mc.resources_created.labels(resource_type="dashboard").inc()
         mc.dashboards_generated.labels(layout_type=layout_type).inc()
         return log.collect(json.dumps(result, indent=2))
     except httpx.HTTPStatusError as e:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_generate_dashboard", status="error").inc()
         mc.record_error(tool="superset_generate_dashboard", error_message=f"HTTP {e.response.status_code} generating dashboard", status_code=e.response.status_code)
         return log.collect(DashboardError(
             f"HTTP {e.response.status_code} generating dashboard",
             status_code=e.response.status_code,
             details=e.response.text,
         ).to_json())
     except Exception as e:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_generate_dashboard", status="error").inc()
         mc.record_error(tool="superset_generate_dashboard", error_message=str(e))
         return log.collect(DashboardError(f"Unexpected error generating dashboard: {e}", details=str(e)).to_json())


def _build_simple_layout_json(chart_ids: List[int]) -> str:
    """
    Build a simple row layout JSON string from a list of chart IDs.

    Internal helper for generate_dashboard that creates a flat row/column
    layout without fetching chart metadata from the server.

    Args:
        chart_ids: List of chart IDs to arrange in the layout.

    Returns:
        JSON string of the position_json layout.
    """
    chart_info = []
    for cid in chart_ids:
        chart_info.append({
            "id": cid,
            "name": f"Chart {cid}"
        })
    layout = _build_simple_layout(chart_info, "row_of_charts", 6, 50)
    return json.dumps(layout)


def _build_robust_layout_json(chart_ids: List[int]) -> str:
    """
    Build a robust nested layout JSON string from a list of chart IDs.

    Internal helper for generate_dashboard that creates a hierarchical
    layout with auto-sizing without fetching chart metadata.

    Args:
        chart_ids: List of chart IDs to arrange in the layout.

    Returns:
        JSON string of the position_json layout.
    """
    chart_info = []
    for cid in chart_ids:
        chart_info.append({
            "id": cid,
            "name": f"Chart {cid}"
        })
    layout = rules.generate_robust_dashboard_layout(chart_info)
    return json.dumps(layout)


async def add_chart_to_existing_dashboard(
    manager: ConnectionManager,
    server_id: str,
    dashboard_id: int,
    chart_id: int
) -> str:
    """
    MCP Tool: superset_add_chart_to_existing_dashboard - Add a chart to a dashboard.

    Appends a chart to an existing dashboard by modifying the dashboard's
    position_json layout, updating the dashboard via PUT, and linking the
    chart to the dashboard via the chart API.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        dashboard_id: The numeric ID of the target dashboard.
        chart_id: The numeric ID of the chart to add.

    Returns:
        JSON string with a success message, dashboard_id, chart_id, and the
        updated dashboard result. Returns DashboardError if the server/dashboard
            is not found or the API request fails.

    Example:
        result = await add_chart_to_existing_dashboard(
            manager, "default", dashboard_id=789, chart_id=123
        )
        # Returns JSON with success message, dashboard_id, chart_id, and updated result.
    """
    # Step 1: Validate server context exists
    ctx = manager.get_context(server_id)
    if not ctx:
        return log.collect(DashboardError(f"Server '{server_id}' not found.", status_code=404).to_json())

    # Step 1b: Validate chart columns before adding to dashboard
    try:
        chart_raw = await impl_get_resource(manager, server_id, "chart", chart_id)
        chart_data = json.loads(chart_raw)
        chart_result = chart_data.get("result", {})
        chart_params = chart_result.get("params", {})
        datasource_id = chart_result.get("datasource_id")
        viz_type = chart_result.get("viz_type", "")
        slice_name = chart_result.get("slice_name", f"Chart {chart_id}")

        if datasource_id:
            if isinstance(chart_params, str):
                try:
                    chart_params = json.loads(chart_params)
                except (json.JSONDecodeError, TypeError):
                    chart_params = {}

            ds_raw = await impl_superset_api(
                manager, server_id, "GET", f"/api/v1/dataset/{datasource_id}"
            )
            ds_data = json.loads(ds_raw)
            dataset_columns = ds_data.get("result", {}).get("columns", [])

            if dataset_columns:
                validation = validate_chart_data_against_dataset(
                    chart_params, dataset_columns, viz_type
                )
                if not validation["is_valid"]:
                    error_msg = format_validation_error(validation, slice_name, datasource_id)
                    return log.collect(DashboardError(
                        error_msg["title"],
                        details=error_msg["body"],
                        status_code=400,
                    ).to_json())
    except Exception as e:
        return log.collect(DashboardError(
            f"Failed to validate chart {chart_id} columns: {e}",
            status_code=500,
        ).to_json())

    try:
        # Step 2: Fetch the current dashboard configuration
        dash_str = await impl_get_resource(manager, server_id, "dashboard", dashboard_id)
        dash_data = json.loads(dash_str)

        if "Error" in dash_str or "not found" in dash_str.lower():
            return log.collect(DashboardError(f"Dashboard '{dashboard_id}' not found", details=dash_str).to_json())

        dash_result = dash_data.get("result", {})
        position_json_raw = dash_result.get("position_json", "{}")

        # Step 3: Normalize position_json to dict form (handles both dict and JSON string)
        if isinstance(position_json_raw, dict):
            position_json = position_json_raw
        else:
            try:
                position_json = json.loads(position_json_raw)
            except (json.JSONDecodeError, TypeError):
                position_json = {}

        # Step 4: Append the new chart element to the layout
        position_json = _add_chart_to_position_json(position_json, chart_id)

        update_payload = {
            "position_json": json.dumps(position_json)
        }

        # Step 5: Update the dashboard with the modified position_json
        endpoint = f"/api/v1/dashboard/{dashboard_id}"
        resp = await execute_request(ctx, "PUT", endpoint, json=update_payload)
        resp.raise_for_status()

        # Step 6: Link the chart to the dashboard via the chart API
        await bulk_link_charts(manager, server_id, dashboard_id, [chart_id])

        dash_title = dash_result.get("dashboard_title", f"Dashboard {dashboard_id}")
        result_data = resp.json()

        # Step 7: Generate Mermaid graph for the updated dashboard
        try:
            existing_charts = dash_result.get("charts", [])
            chart_names = [c.get("slice_name", f"Chart {c.get('id')}") for c in existing_charts]
            chart_names.append(f"Chart {chart_id}")
            result_data["_mermaid_graph"] = dashboard_to_mermaid(
                dash_title,
                chart_info=[{"slice_name": name} for name in chart_names],
            )
        except Exception:
            result_data["_mermaid_graph"] = None

        return log.collect(json.dumps({
            "message": "Chart successfully added to dashboard",
            "dashboard_id": dashboard_id,
            "chart_id": chart_id,
            "result": result_data
        }, indent=2))

    except httpx.HTTPStatusError as e:
        return log.collect(DashboardError(
            f"HTTP {e.response.status_code} adding chart to dashboard",
            status_code=e.response.status_code,
            details=e.response.text,
        ).to_json())
    except Exception as e:
        return log.collect(DashboardError(f"Unexpected error adding chart to dashboard: {e}", details=str(e)).to_json())


def _add_chart_to_position_json(position_json: Dict, chart_id: int) -> Dict:
    """
    Add a chart element to the position JSON layout.

    Finds the GRID component, creates a new ROW, and appends a CHART
    element with the given chart_id inside it. Uses consistent UUID-based
    IDs for compatibility with Superset's dashboard v2 format.

    Args:
        position_json: Existing dashboard position JSON dict.
        chart_id: The numeric chart ID to add.

    Returns:
        The modified position JSON dict with the new chart element added.
    """
    import time
    import uuid

    # Step 1: Generate unique IDs for the new chart element and its row
    dashboard_uuid = str(uuid.uuid4())[:8]
    chart_element_id = f"CHART-{dashboard_uuid}-{chart_id}"
    row_id = f"ROW-R{int(time.time()) % 10000}-{dashboard_uuid}"

    # Step 2: Find the GRID component to attach the new row underneath
    grid_id = None
    for key, value in position_json.items():
        if isinstance(value, dict) and value.get("type") == "GRID":
            grid_id = key
            # Ensure GRID_ID has parents field
            if "parents" not in value:
                value["parents"] = ["ROOT_ID"]
            break
    
    if grid_id:
        # Add a new row
        position_json[row_id] = {
            "type": "ROW",
            "id": row_id,
            "children": [],
            "parents": [grid_id],
            "meta": {"background": "BACKGROUND_TRANSPARENT"}
        }
        position_json[grid_id]["children"].append(row_id)
        
        # Add chart to the row
        position_json[chart_element_id] = {
            "type": "CHART",
            "id": chart_element_id,
            "children": [],
            "parents": [row_id],
            "meta": {
                "chartId": chart_id,
                "width": 6,
                "height": 50,
                "startX": 0,
                "startY": 0,
                "sliceName": f"Chart {chart_id}"
            }
        }
        position_json[row_id]["children"].append(chart_element_id)
    
    return position_json

def _extract_chart_ids_from_position_json(position_json: Union[str, Dict]) -> List[int]:
    """Extract all chart IDs from a position JSON string or dict.
    
    Supports both formats:
      - {"meta": {"chartId": 296, ...}}  (generated by our layout builders)
      - {"slice_id": 296}                 (legacy format)
    """
    chart_ids = []
    try:
        # Step 1: Normalize input to dict form (accepts both str and dict)
        if isinstance(position_json, str):
            pos = json.loads(position_json)
        else:
            pos = position_json

        # Step 2: Recursive walker traverses dicts/lists looking for chart IDs
        def walk(obj):
            """Recursively traverse dicts/lists to find chartId and slice_id entries.

            Args:
                obj: A dict or list to traverse for chart IDs.
            """
            if isinstance(obj, dict):
                if "chartId" in obj and isinstance(obj["chartId"], int):
                    chart_ids.append(obj["chartId"])
                elif "slice_id" in obj and isinstance(obj["slice_id"], int):
                    chart_ids.append(obj["slice_id"])
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)
        
        walk(pos)
    except (json.JSONDecodeError, TypeError):
        pass
    
    # Deduplicate while preserving order
    seen = set()
    return [x for x in chart_ids if not (x in seen or seen.add(x))]


def _validate_position_json_structure(position_json: Union[str, Dict]) -> List[str]:
    """
    Validate the structural integrity of a dashboard position JSON.
    
    Checks:
      - Every CHART component has a valid meta.chartId (integer)
      - No CHART is placed directly under GRID_ID (must be inside a ROW)
      - Every component has 'type' and 'children' fields
    
    Returns list of error messages. Empty list = valid.
    """
    errors: List[str] = []

    # Step 1: Parse the position JSON (accepts both string and dict)
    try:
        if isinstance(position_json, str):
            pos = json.loads(position_json)
        else:
            pos = position_json
    except (json.JSONDecodeError, TypeError) as e:
        return [f"Position JSON is not valid JSON: {e}"]

    if not isinstance(pos, dict):
        return ["Position JSON must be a dict"]

    # Step 2: Check for required top-level keys
    if "DASHBOARD_VERSION_KEY" not in pos:
        errors.append("Missing DASHBOARD_VERSION_KEY in position JSON")
    
    if "ROOT_ID" not in pos:
        errors.append("Missing ROOT_ID in position JSON")
        return errors
    root = pos["ROOT_ID"]
    if not isinstance(root, dict):
        errors.append(f"ROOT_ID must be a dict/object, got {type(root).__name__}: {root!r}")
    elif root.get("type") != "ROOT":
        errors.append("ROOT_ID must have type='ROOT'")
    if isinstance(root, dict) and "GRID_ID" not in root.get("children", []):
        errors.append("ROOT_ID.children must contain 'GRID_ID'")
    if "GRID_ID" not in pos:
        errors.append("Missing GRID_ID in position JSON")
        return errors
    grid = pos["GRID_ID"]
    if not isinstance(grid, dict):
        errors.append(f"GRID_ID must be a dict/object, got {type(grid).__name__}: {grid!r}")
    elif grid.get("type") != "GRID":
        errors.append("GRID_ID must have type='GRID'")
    
    grid_children = grid.get("children", []) if isinstance(grid, dict) else []
    missing_types: List[str] = []
    unknown_types: List[str] = []
    invalid_chart_ids: List[str] = []
    charts_under_grid: List[str] = []

    # Step 3: Iterate over all components (excluding top-level keys) to validate structure
    for key, component in pos.items():
        if key in ("DASHBOARD_VERSION_KEY", "ROOT_ID", "GRID_ID"):
            continue
        if not isinstance(component, dict):
            continue
        
        comp_type = component.get("type")
        if not comp_type:
            missing_types.append(key)
            continue
        
        comp_id = component.get("id", key)
        
        if comp_type == "CHART":
            meta = component.get("meta", {})
            chart_id = meta.get("chartId") if isinstance(meta, dict) else None
            if not isinstance(chart_id, int):
                invalid_chart_ids.append(f"Component '{key}' ({comp_id}): meta.chartId must be an integer, got {type(chart_id).__name__ if chart_id is not None else 'None'}")
            if key in grid_children:
                charts_under_grid.append(f"Component '{key}' ({comp_id}): CHART placed directly under GRID_ID, must be inside a ROW")
        
        if comp_type not in ("ROW", "CHART", "HEADER", "TAB", "DIVIDER", "MARKDOWN", "DYNAMIC_TYPE"):
            unknown_types.append(f"Component '{key}' has unknown type '{comp_type}'")
        
        if "children" not in component:
            errors.append(f"Component '{key}' ({comp_id}) is missing 'children' field")
    
    errors.extend(missing_types)
    errors.extend(invalid_chart_ids)
    errors.extend(charts_under_grid)
    errors.extend(unknown_types)
    
    return errors


async def _validate_charts_exist(manager: ConnectionManager, server_id: str, chart_ids: List[int]) -> List[int]:
    """
    Validate that all chart IDs exist on the Superset server.
    
        Returns list of chart IDs that were not found.
    """
    # Step 1: Retrieve server context
    ctx = manager.get_context(server_id)
    if not ctx:
        return chart_ids

    # Step 2: Fetch all charts from the server (paginated)
    all_charts = []
    page = 1
    page_size = 100

    while True:
        try:
            resp = await ctx.client.get("/api/v1/chart/", params={"page_size": page_size, "page": page})
            if resp.status_code != 200:
                break
            data = resp.json().get("result", [])
            if not data:
                break
            all_charts.extend(data)
            if len(data) < page_size:
                break
            page += 1
        except Exception:
            break

    # Step 3: Compare requested IDs against existing ones
    existing_ids = {c["id"] for c in all_charts}
    return [cid for cid in chart_ids if cid not in existing_ids]


async def _validate_chart_data_endpoint(manager: ConnectionManager, server_id: str, chart_id: int) -> Dict[str, Any]:
    """
    Test a single chart's data endpoint to verify it actually renders.

    Delegates to the blunt version in charts.py that blocks on ANY sign of trouble.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_id: The numeric ID of the chart to test.

    Returns:
        Dict with is_valid, error, row_count, and viz_type keys.
    """
    # Step 1: Import and delegate to the charts module's data endpoint tester
    from modules.SupersetModule.tools.charts import _test_chart_data_endpoint
    result = await _test_chart_data_endpoint(manager, server_id, chart_id)
    # Step 2: Add viz_type placeholder (populated by caller)
    result["viz_type"] = None
    return result


async def _get_chart_info(manager: ConnectionManager, server_id: str, chart_id: int) -> Optional[Dict[str, Any]]:
    """Get chart info including viz_type from Superset API.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_id: The numeric ID of the chart to inspect.

    Returns:
        Dict with id, viz_type, and slice_name keys, or None if the chart
        cannot be retrieved.
    """
    # Step 1: Retrieve server context
    ctx = manager.get_context(server_id)
    if not ctx:
        return None

    try:
        # Step 2: Fetch chart metadata from the API
        resp = await execute_request(ctx, "GET", f"/api/v1/chart/{chart_id}")
        chart = resp.json().get("result", {})
        return {
            "id": chart.get("id"),
            "viz_type": chart.get("viz_type"),
            "slice_name": chart.get("slice_name"),
        }
    except Exception:
        return None


async def _pre_validate_chart_data(manager: ConnectionManager, server_id: str, chart_ids: List[int]) -> List[Dict[str, Any]]:
    """
    Pre-validate all charts before dashboard creation by testing their data endpoints.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_ids: List of chart IDs to validate.

    Returns:
        List of validation result dicts for failed charts, each with chart_id,
        viz_type, slice_name, and error keys. Empty list means all valid.
    """
    failed_charts = []

    for chart_id in chart_ids:
        # Step 1: Get chart metadata (viz_type, name) for context in error messages
        chart_info = await _get_chart_info(manager, server_id, chart_id)
        viz_type = chart_info.get("viz_type", "unknown") if chart_info else "unknown"
        slice_name = chart_info.get("slice_name", f"Chart {chart_id}") if chart_info else f"Chart {chart_id}"

        # Step 2: Test the chart's data endpoint to verify it actually renders
        validation = await _validate_chart_data_endpoint(manager, server_id, chart_id)

        # Step 3: If chart fails validation, collect error details for reporting
        if not validation["is_valid"]:
            failed_charts.append({
                "chart_id": chart_id,
                "viz_type": viz_type,
                "slice_name": slice_name,
                "error": validation["error"],
            })

    return failed_charts
