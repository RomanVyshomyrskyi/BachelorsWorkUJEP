"""Dashboard CRUD operations for Apache Superset.

Provides functions for creating, updating, and retrieving dashboard information.
"""
import json
import httpx
import time
import logging
from typing import Optional, List

from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.exceptions import DashboardError
from modules.SupersetModule.superset_mermaid import dashboard_to_mermaid
from modules.log_utils import LogCollector
from modules.metrics import get_metrics
from modules.SupersetModule import rules

log = LogCollector(__name__)
logger = logging.getLogger(__name__)


async def get_dashboard_info(
    manager: ConnectionManager,
    server_id: str,
    dashboard_id
) -> str:
    """Gets detailed information for a specific dashboard.

    Args:
        server_id: The ID of the configured Superset server.
        dashboard_id: The ID of the dashboard to retrieve.
    Returns:
        JSON string containing the dashboard details.

    Examples:
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

     Examples:
         result = await create_dashboard(
             manager, "default",
             dashboard_title="Sales Dashboard",
             position_json='{"DASHBOARD_VERSION_KEY": "v2", "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]}}',
             published=True
         )
         # Returns JSON with created dashboard details, ID, and Mermaid graph.
     """
     ctx = manager.get_context(server_id)
     if not ctx:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_create_dashboard", status="error").inc()
         mc.record_error(tool="superset_create_dashboard", error_message=f"Server '{server_id}' not found.")
         return log.collect(DashboardError(f"Server '{server_id}' not found.", status_code=404).to_json())

     from modules.SupersetModule.tools.dashboard.layout import _extract_chart_ids_from_position_json, _validate_position_json_structure
     chart_ids = _extract_chart_ids_from_position_json(position_json)

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

     if chart_ids:
         from modules.SupersetModule.tools.dashboard.chart_validators import _validate_charts_exist, _pre_validate_chart_data
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

    Examples:
        result = await get_dashboard_api_info(manager, "default")
        # Returns JSON with dashboard API metadata including supported features and filters.
    """
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

    Examples:
        result = await update_dashboard(
            manager, "default", dashboard_id=789,
            json_body='{"dashboard_title": "Updated Dashboard"}'
        )
        # Returns JSON with updated dashboard details.
    """
    return await impl_superset_api(manager, server_id, "PUT", f"/api/v1/dashboard/{dashboard_id}", json_body=json_body)


def get_dashboard_creation_rules() -> str:
    """
    MCP Tool: superset_get_dashboard_creation_rules - Get expert rules for creating dashboards.

    Returns a set of best practices and guidelines for building functional
    Superset dashboards. Includes layout recommendations, chart sizing tips,
    and common pitfalls to avoid.

    Returns:
        String containing the expert rules for dashboard creation.

    Examples:
        result = get_dashboard_creation_rules()
        # Returns string with expert guidelines for dashboard creation.
    """
    return rules.get_dashboard_creation_rules()
