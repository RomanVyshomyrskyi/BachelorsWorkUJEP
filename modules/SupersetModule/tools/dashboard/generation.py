"""Dashboard generation with chart validation.

Provides the main generate_dashboard function.
"""
import json
import httpx
import time
from typing import List, Optional

from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.tools.resources import impl_get_resource
from modules.SupersetModule.exceptions import DashboardError
from modules.SupersetModule.superset_mermaid import dashboard_to_mermaid
from modules.log_utils import LogCollector
from modules.metrics import get_metrics
from modules.SupersetModule.tools.chart_validation import validate_chart_data_against_dataset

log = LogCollector(__name__)


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

     Examples:
         result = await generate_dashboard(
             manager, "default",
             dashboard_title="Sales Dashboard",
             chart_ids=[123, 456],
             layout_type="robust",
             published=True
         )
         # Returns JSON with created dashboard details, ID, and Mermaid graph.
     """
     ctx = manager.get_context(server_id)
     if not ctx:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_generate_dashboard", status="error").inc()
         mc.record_error(tool="superset_generate_dashboard", error_message=f"Server '{server_id}' not found.")
         return log.collect(DashboardError(f"Server '{server_id}' not found.", status_code=404).to_json())

     if not chart_ids:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_generate_dashboard", status="error").inc()
         mc.record_error(tool="superset_generate_dashboard", error_message="At least one chart ID must be provided.")
         return log.collect(DashboardError("At least one chart ID must be provided.").to_json())

     from modules.SupersetModule.tools.dashboard.chart_validators import _validate_charts_exist, _pre_validate_chart_data
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
         from modules.SupersetModule.tools.dashboard.helpers import _build_simple_layout_json, _build_robust_layout_json
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

         endpoint = "/api/v1/dashboard/"
         resp = await execute_request(ctx, "POST", endpoint, json=dashboard_payload)
         resp.raise_for_status()
         result = resp.json()

         from modules.SupersetModule.tools.dashboard.linking import bulk_link_charts
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
