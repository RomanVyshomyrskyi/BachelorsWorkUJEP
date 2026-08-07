"""Chart-to-dashboard linking operations for Apache Superset.

Provides functions for linking charts to existing dashboards,
either individually or in bulk.
"""
import json
import httpx
from typing import List, Dict
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.superset_mermaid import dashboard_to_mermaid
from modules.log_utils import LogCollector
from modules.SupersetModule.exceptions import DashboardError
from modules.SupersetModule.tools.resources import impl_get_resource
from modules.SupersetModule.tools.chart_validation import validate_chart_data_against_dataset, format_validation_error
from modules.SupersetModule.tools.dashboard.layout_helpers import _add_chart_to_position_json

log = LogCollector(__name__)


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
    """
    results = []
    errors = []
    for cid in chart_ids:
        try:
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
        updated dashboard result.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return log.collect(DashboardError(f"Server '{server_id}' not found.", status_code=404).to_json())

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
        dash_str = await impl_get_resource(manager, server_id, "dashboard", dashboard_id)
        dash_data = json.loads(dash_str)

        if "Error" in dash_str or "not found" in dash_str.lower():
            return log.collect(DashboardError(f"Dashboard '{dashboard_id}' not found", details=dash_str).to_json())

        dash_result = dash_data.get("result", {})
        position_json_raw = dash_result.get("position_json", "{}")

        if isinstance(position_json_raw, dict):
            position_json = position_json_raw
        else:
            try:
                position_json = json.loads(position_json_raw)
            except (json.JSONDecodeError, TypeError):
                position_json = {}

        position_json = _add_chart_to_position_json(position_json, chart_id)

        update_payload = {
            "position_json": json.dumps(position_json)
        }

        endpoint = f"/api/v1/dashboard/{dashboard_id}"
        resp = await execute_request(ctx, "PUT", endpoint, json=update_payload)
        resp.raise_for_status()

        await bulk_link_charts(manager, server_id, dashboard_id, [chart_id])

        dash_title = dash_result.get("dashboard_title", f"Dashboard {dashboard_id}")
        result_data = resp.json()

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
