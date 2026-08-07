"""
Chart lifecycle management: delete, validate_on_datasource, verify_params_saved.

Contains _delete_chart, _validate_chart_on_datasource, _verify_chart_params_saved.
"""

import json
import logging
from typing import Dict, Any, List
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.superset_validation import validate_datasource_compatibility

from .helpers import logger

logger = logging.getLogger(__name__)


async def _delete_chart(
    manager,
    server_id: str,
    chart_id: int
) -> bool:
    """
    Delete a chart by its ID via the Superset API.

    Used internally after chart creation fails post-creation validation
    to clean up the partially-created chart.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_id: The numeric ID of the chart to delete.

    Returns:
        True if the DELETE request returned HTTP 200 or 204, False otherwise
        (including any exception during the request).
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return False

    try:
        resp = await execute_request(ctx, "DELETE", f"/api/v1/chart/{chart_id}")
        return resp.status_code in [200, 204]
    except Exception:
        return False


async def _validate_chart_on_datasource(
    manager,
    server_id: str,
    chart_id: int
) -> Dict[str, Any]:
    """
    Validate an existing chart against its datasource configuration.

    Fetches the chart's params and datasource, checks datasource compatibility,
    and tests the data endpoint. Used for validating charts before adding them
    to dashboards.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_id: The numeric ID of the chart to validate.

    Returns:
        Dict with keys:
          - chart_id (int): The chart ID that was validated
          - is_valid (bool): True if all validations passed
          - error (str|None): Error description if invalid
          - viz_type (str|None): The chart's viz_type if available
          - row_count (int|None): Rows returned by data endpoint if valid
    """
    # Local import to avoid circular dependency
    from .data import _test_chart_data_endpoint

    ctx = manager.get_context(server_id)
    if not ctx:
        return {"chart_id": chart_id, "is_valid": False, "error": "Server not found"}

    try:
        resp = await execute_request(ctx, "GET", f"/api/v1/chart/{chart_id}")
        chart = resp.json().get("result", {})
        viz_type = chart.get("viz_type", "unknown")
        params_str = chart.get("params", "{}")

        try:
            params = json.loads(params_str)
        except json.JSONDecodeError:
            params = {}

        dataset_id = chart.get("datasource_id")

        try:
            ds_resp = await execute_request(ctx, "GET", f"/api/v1/dataset/{dataset_id}")
            ds = ds_resp.json().get("result", {})
            columns = ds.get("columns", [])
        except Exception:
            columns = []

        compat_errors = validate_datasource_compatibility(viz_type, params, columns)

        if compat_errors:
            return {
                "chart_id": chart_id,
                "is_valid": False,
                "error": "Compatibility: " + "; ".join(compat_errors),
                "viz_type": viz_type,
            }

        data_result = await _test_chart_data_endpoint(manager, server_id, chart_id)

        if not data_result["is_valid"]:
            return {
                "chart_id": chart_id,
                "is_valid": False,
                "error": f"Data test failed: {data_result['error']}",
                "viz_type": viz_type,
            }

        return {
            "chart_id": chart_id,
            "is_valid": True,
            "error": None,
            "viz_type": viz_type,
            "row_count": data_result["row_count"],
        }
    except Exception as e:
        return {
            "chart_id": chart_id,
            "is_valid": False,
            "error": f"Validation error: {str(e)[:200]}",
        }


async def _verify_chart_params_saved(
    manager,
    server_id: str,
    chart_id: int
) -> List[str]:
    """
    Verify that a chart's saved params have no null/empty values for critical fields.

    After chart creation, fetches the chart from Superset and inspects the stored
    params. This catches cases where Superset's API silently accepted bad params
    (e.g., null metric reference) and stored them, which later cause render-time errors.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_id: The numeric ID of the chart to verify.

    Returns:
        List of error strings. Empty list means all saved params are valid.
        Each string describes a specific field that has null/empty values.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return ["Server context not found"]

    try:
        resp = await execute_request(ctx, "GET", f"/api/v1/chart/{chart_id}")
        chart = resp.json().get("result", {})
        params_str = chart.get("params", "{}")

        try:
            params = json.loads(params_str)
        except (json.JSONDecodeError, TypeError):
            return [f"Chart params is not valid JSON: {params_str[:100]}"]

        errors: List[str] = []

        if "metric" in params:
            m = params["metric"]
            if m is None:
                errors.append("saved 'metric' is null")
            elif isinstance(m, dict):
                col_name = m.get("column", {}).get("column_name")
                if col_name is None:
                    errors.append("saved 'metric' has null column_name")

        if "metrics" in params and isinstance(params["metrics"], list):
            for i, m in enumerate(params["metrics"]):
                if m is None:
                    errors.append(f"saved 'metrics[{i}]' is null")
                elif isinstance(m, dict):
                    col_name = m.get("column", {}).get("column_name")
                    if col_name is None:
                        errors.append(f"saved 'metrics[{i}]' has null column_name")

        if "orderby" in params and isinstance(params["orderby"], list):
            for i, entry in enumerate(params["orderby"]):
                if isinstance(entry, list) and len(entry) >= 1 and entry[0] is None:
                    errors.append(f"saved 'orderby[{i}]' has null column reference")
                elif isinstance(entry, dict):
                    col_entry = entry.get("column", {})
                    if isinstance(col_entry, dict) and col_entry.get("column_name") is None:
                        errors.append(f"saved 'orderby[{i}]' has null column_name")

        if "timeseries_limit_metric" in params and params["timeseries_limit_metric"] is None:
            errors.append("saved 'timeseries_limit_metric' is null")

        if "entity" in params and not params["entity"]:
            errors.append("saved 'entity' is null or empty")

        if "columns" in params and isinstance(params["columns"], list):
            for i, col in enumerate(params["columns"]):
                if col is None:
                    errors.append(f"saved 'columns[{i}]' is null")
                elif isinstance(col, str) and not col.strip():
                    errors.append(f"saved 'columns[{i}]' is empty")

        if "all_columns" in params and isinstance(params["all_columns"], list):
            for i, col in enumerate(params["all_columns"]):
                if col is None:
                    errors.append(f"saved 'all_columns[{i}]' is null")
                elif isinstance(col, str) and not col.strip():
                    errors.append(f"saved 'all_columns[{i}]' is empty")

        if "groupby" in params and isinstance(params["groupby"], list):
            for i, col in enumerate(params["groupby"]):
                if col is None:
                    errors.append(f"saved 'groupby[{i}]' is null")
                elif isinstance(col, str) and not col.strip():
                    errors.append(f"saved 'groupby[{i}]' is empty")

        viz_type = chart.get("viz_type", "")
        time_based_types = {
            "echarts_timeseries_line", "echarts_timeseries_bar", "echarts_area",
            "echarts_timeseries_scatter", "mixed_timeseries", "waterfall",
            "big_number", "box_plot",
        }
        if viz_type in time_based_types:
            if not params.get("granularity_sqla") and not params.get("x_axis"):
                errors.append(
                    f"saved chart is time-based ({viz_type}) but has no "
                    f"'granularity_sqla' or 'x_axis' — requires a datetime column"
                )

        return errors

    except Exception as e:
        return [f"Could not verify chart params: {str(e)[:200]}"]
