"""
Create chart operation: create_chart.

Creates a new Superset chart with full validation pipeline.
"""

import json
import time
import logging
import httpx
from typing import Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.exceptions import ChartError
from modules.SupersetModule.superset_validation import (
    validate_chart_params,
    auto_fix_chart_params,
    format_error_summary,
)
from modules.SupersetModule.superset_mermaid import chart_to_mermaid
from modules.SupersetModule.resolver import resolve_chart_params
from modules.SupersetModule.tools.chart_validation import (
    validate_chart_data_against_dataset,
    format_validation_error,
)
from modules.metrics import get_metrics
from .helpers import logger
from .cache import (
    _ensure_chart_types_cached,
    _is_known_chart_type,
)
from .resolution import (
    _resolve_viz_type,
    _validate_sankey_params,
)
from .validation import (
    _validate_metric_string_format,
    _validate_metrics_against_dataset,
)
from .lifecycle import _delete_chart, _verify_chart_params_saved

logger = logging.getLogger(__name__)


async def create_chart(
    manager: ConnectionManager,
    server_id: str,
    slice_name: str,
    viz_type: str,
    datasource_id: int,
    datasource_type: str,
    params: str,
    description: Optional[str] = None,
    skip_data_test: bool = False
 ) -> str:
    """
    MCP Tool: superset_create_chart - Create a new Superset chart with full validation.

    This is the primary chart creation tool. It performs extensive pre-validation
    including: viz_type existence check, metric validation against dataset columns,
    datasource compatibility check, column-level validation, Sankey cycle detection,
    and structural parameter validation. After creation, it verifies saved params
    and tests the data endpoint to catch any issues Superset may have silently accepted.

    The chart is ONLY created if ALL validation passes. If any check fails, the
    tool returns a detailed error with suggestions for fixing the params.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server where the chart will be created.
        slice_name: The display name for the chart in Superset's UI.
        viz_type: The chart type. Can be a shorthand alias ('bar', 'line', 'pie', 'table',
            'scatter') or a full Superset viz_type string. Must be known to Superset.
        datasource_id: The numeric ID of the dataset to use as the chart's datasource.
        datasource_type: The type of datasource, e.g., 'table' for physical/virtual datasets.
        params: JSON string of chart configuration parameters. Must include metric references,
            groupby fields, and any viz_type-specific settings. Must reference valid columns
            from the datasource.
        description: Optional human-readable description of the chart's purpose.

    Returns:
        JSON string containing the created chart's details (ID, name, URL, params) on success,
        or a ChartError JSON with detailed error message and fix suggestions on failure.

    Example:
        result = await create_chart(
            manager, "default",
            slice_name="Monthly Sales",
            viz_type="bar",
            datasource_id=42,
            datasource_type="table",
            params='{"metrics": ["SUM(sales)"], "groupby": ["region"]}'
        )
        # Returns JSON with created chart ID, name, URL, and params.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_create_chart", status="error").inc()
        mc.record_error(tool="superset_create_chart", error_message=f"Server '{server_id}' not found.")
        return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    known_types = await _ensure_chart_types_cached(manager, server_id)

    start_time = time.monotonic()
    try:
        actual_viz_type = _resolve_viz_type(viz_type)

        if not _is_known_chart_type(known_types, actual_viz_type):
            mc = get_metrics()
            mc.tool_calls.labels(tool="superset_create_chart", status="error").inc()
            mc.record_error(tool="superset_create_chart", error_message=f"Unknown chart type '{actual_viz_type}'")
            return ChartError(
                f"Chart type '{actual_viz_type}' is not recognized.",
                details=f"Please call 'superset_get_all_chart_schemas' first to discover all available chart types. Known types: {', '.join(known_types[:20])}{'...' if len(known_types) > 20 else ''}",
            ).to_json()
        params_dict = json.loads(params) if params else {}
        fixed_params = auto_fix_chart_params(actual_viz_type, params_dict)

        dataset_columns = []
        dataset_metrics = []
        dataset_fetch_error = None
        try:
            dataset_response = await impl_superset_api(manager, server_id, "GET", f"/api/v1/dataset/{datasource_id}")
            dataset_data = json.loads(dataset_response)
            dataset_columns = dataset_data.get("result", {}).get("columns", [])
            dataset_metrics = dataset_data.get("result", {}).get("metrics", [])
        except Exception as e:
            dataset_fetch_error = str(e)

        from modules.SupersetModule.superset_validation import NO_METRICS_TYPES
        if dataset_fetch_error and actual_viz_type not in NO_METRICS_TYPES:
            mc = get_metrics()
            mc.tool_calls.labels(tool="superset_create_chart", status="error").inc()
            mc.record_error(
                tool="superset_create_chart",
                error_message=f"Dataset schema fetch failed for datasource {datasource_id}"
            )
            return ChartError(
                f"Chart creation blocked: cannot validate columns for datasource {datasource_id}",
                details=(
                    f"Failed to fetch dataset schema for datasource {datasource_id}. "
                    f"Column validation is required before chart creation to prevent "
                    f"broken charts.\n\n"
                    f"Error: {dataset_fetch_error}\n\n"
                    f"Verify that datasource {datasource_id} exists and has columns defined."
                ),
                status_code=400,
            ).to_json()

        metric_errors = _validate_metrics_against_dataset(
            fixed_params, dataset_metrics, actual_viz_type, dataset_columns
        )

        if not dataset_columns and not dataset_metrics and not metric_errors:
            metric_errors = _validate_metric_string_format(fixed_params)
        if metric_errors:
            mc = get_metrics()
            mc.tool_calls.labels(tool="superset_create_chart", status="error").inc()
            mc.record_error(
                tool="superset_create_chart",
                error_message=f"Metrics validation failed: {len(metric_errors)} errors"
            )
            available = ", ".join(m['metric_name'] for m in dataset_metrics) if dataset_metrics else "(no predefined metrics)"
            return ChartError(
                "Chart creation blocked: Metric validation failed",
                details=(
                    f"Chart '{slice_name}' cannot be created — metric validation found "
                    f"{len(metric_errors)} issue(s):\n\n"
                    + "\n\n".join(f"  {i+1}. {m}" for i, m in enumerate(metric_errors))
                    + f"\n\nAvailable metrics: {available}"
                ),
                status_code=400,
            ).to_json()

        if dataset_columns:
            fixed_params, column_warnings = resolve_chart_params(fixed_params, dataset_columns)
            if column_warnings:
                warning = "Column name fixes: " + "; ".join(column_warnings)
            else:
                warning = None

            sankey_warning = _validate_sankey_params(fixed_params, slice_name)
            if sankey_warning:
                return ChartError(
                    sankey_warning["title"],
                    details=sankey_warning["body"],
                    status_code=400,
                ).to_json()

            logger.info(f"Running pre-chart data validation for datasource_id={datasource_id}")
            validation_result = validate_chart_data_against_dataset(
                fixed_params, dataset_columns, actual_viz_type
            )

            if not validation_result["is_valid"]:
                logger.warning(
                    f"Chart validation failed for '{slice_name}': "
                    f"{len(validation_result['errors'])} errors, "
                    f"{len(validation_result['missing_columns'])} missing columns"
                )
                error_msg = format_validation_error(validation_result, slice_name, datasource_id)

                mc = get_metrics()
                mc.tool_calls.labels(tool="superset_create_chart", status="error").inc()
                mc.record_error(
                    tool="superset_create_chart",
                    error_message=f"Missing columns in dataset: {len(validation_result['missing_columns'])} columns not found"
                )

                return ChartError(
                    error_msg["title"],
                    details=error_msg["body"],
                    status_code=400,
                ).to_json()

            if validation_result.get("warnings"):
                validation_warnings = "; ".join(validation_result["warnings"])
                if warning:
                    warning = warning + " | Validation: " + validation_warnings
                else:
                    warning = "Validation: " + validation_warnings
        else:
            warning = None
            logger.warning(
                f"Dataset columns not available for datasource_id={datasource_id}. "
                f"Metric validation already ran; chart will be tested via data endpoint."
            )

        if dataset_columns:
            from modules.SupersetModule.superset_validation import validate_datasource_compatibility
            compat_errors = validate_datasource_compatibility(actual_viz_type, fixed_params, dataset_columns)
            if compat_errors:
                mc = get_metrics()
                mc.tool_calls.labels(tool="superset_create_chart", status="error").inc()
                mc.record_error(
                    tool="superset_create_chart",
                    error_message=f"Datasource compatibility: {len(compat_errors)} issues"
                )
                return ChartError(
                    f"Chart datasource incompatible: {actual_viz_type}",
                    details=(
                        f"Chart '{slice_name}' cannot be created — datasource is incompatible:\n\n"
                        + "\n".join(f"  {i+1}. {e}" for i, e in enumerate(compat_errors))
                    ),
                    status_code=400,
                ).to_json()

        errors = validate_chart_params(actual_viz_type, fixed_params)
        validation_errors = format_error_summary(errors) if errors else None

        if validation_errors:
            if warning:
                warning = warning + " | " + validation_errors
            else:
                warning = "Validation: " + validation_errors

        if "datasource_id" not in fixed_params or fixed_params["datasource_id"] is None:
            fixed_params["datasource_id"] = datasource_id
        if "datasource" not in fixed_params:
            fixed_params["datasource"] = f"{datasource_id}__table"
        if "datasource_type" not in fixed_params:
            fixed_params["datasource_type"] = datasource_type

        # Final safeguard: bubble_v2 size MUST be SIMPLE metric (not DIMENSION)
        if actual_viz_type == "bubble_v2" and "size" in fixed_params and isinstance(fixed_params["size"], dict):
            size_val = fixed_params["size"]
            if size_val.get("expressionType") == "DIMENSION" or "expressionType" not in size_val:
                col = size_val.get("column", {}).get("column_name", size_val.get("column_name", "count"))
                if isinstance(col, dict):
                    col = col.get("column_name", "count")
                fixed_params["size"] = {
                    "aggregate": "AVG",
                    "column": {"column_name": col},
                    "expressionType": "SIMPLE",
                    "label": f"AVG({col})",
                }

        chart_payload = {
            "slice_name": slice_name,
            "description": description,
            "viz_type": actual_viz_type,
            "datasource_id": datasource_id,
            "datasource_type": datasource_type,
            "params": json.dumps(fixed_params),
        }

        endpoint = "/api/v1/chart/"
        resp = await execute_request(ctx, "POST", endpoint, json=chart_payload)
        resp.raise_for_status()
        result = resp.json()

        chart_id = result.get("id") or result.get("result", {}).get("id", 0)
        params_errors = await _verify_chart_params_saved(manager, server_id, chart_id)
        if params_errors:
            deleted = await _delete_chart(manager, server_id, chart_id)
            mc = get_metrics()
            mc.tool_calls.labels(tool="superset_create_chart", status="error").inc()
            mc.record_error(
                tool="superset_create_chart",
                error_message=f"Chart saved params invalid: {params_errors[0][:100]}"
            )
            return ChartError(
                f"Chart created but params are invalid: {actual_viz_type}",
                details=(
                    f"Chart '{slice_name}' was created (ID: {chart_id}) but the saved params "
                    f"contain null/empty values. Chart was deleted.\n\n"
                    f"Errors:\n" + "\n".join(f"  - {e}" for e in params_errors) + "\n\n"
                    f"Check that all metric, column, and entity references are valid for datasource {datasource_id}."
                ),
                status_code=500,
            ).to_json()

        if not skip_data_test:
            from .data import _test_chart_data_endpoint
            data_test = await _test_chart_data_endpoint(manager, server_id, chart_id)
            if not data_test["is_valid"]:
                deleted = await _delete_chart(manager, server_id, chart_id)
                error_detail = data_test["error"]
                mc = get_metrics()
                mc.tool_calls.labels(tool="superset_create_chart", status="error").inc()
                mc.record_error(
                    tool="superset_create_chart",
                    error_message=f"Chart created but data endpoint failed: {error_detail[:100]}"
                )
                return ChartError(
                    f"Chart created but fails to render: {actual_viz_type}",
                    details=(
                        f"Chart '{slice_name}' was created (ID: {chart_id}) but the data endpoint failed.\n"
                        f"Chart was deleted to avoid leaving broken charts.\n\n"
                        f"Error: {error_detail}\n\n"
                        f"Check that:\n"
                        f"  1. datasource_id {datasource_id} has the right columns\n"
                        f"  2. metrics referenced in params exist in the dataset\n"
                        f"  3. viz_type '{actual_viz_type}' is compatible with the datasource"
                    ),
                    status_code=500,
                ).to_json()

        if warning:
            result["_validation_warning"] = warning

        try:
            result["_mermaid_graph"] = chart_to_mermaid(actual_viz_type, fixed_params, slice_name)
        except Exception:
            result["_mermaid_graph"] = None

        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_create_chart", status="success").inc()
        mc.tool_duration.labels(tool="superset_create_chart").observe(time.monotonic() - start_time)
        mc.resources_created.labels(resource_type="chart").inc()
        return json.dumps(result, indent=2)
    except json.JSONDecodeError as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_create_chart", status="error").inc()
        mc.record_error(tool="superset_create_chart", error_message=f"Invalid JSON in params: {e}")
        return ChartError(f"Invalid JSON in params: {e}", details=str(e)).to_json()
    except httpx.HTTPStatusError as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_create_chart", status="error").inc()
        mc.record_error(tool="superset_create_chart", error_message=f"HTTP {e.response.status_code} creating chart", status_code=e.response.status_code)
        return ChartError(
            f"HTTP {e.response.status_code} creating chart",
            status_code=e.response.status_code,
            details=e.response.text,
        ).to_json()
    except Exception as e:
       return ChartError(f"Unexpected error creating chart: {e}", details=str(e)).to_json()
