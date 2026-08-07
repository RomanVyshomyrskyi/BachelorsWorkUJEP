"""
Generate chart operation: generate_chart.

Generates a chart from a config dict and dataset with full validation.
"""

import json
import time
import logging
import httpx
from typing import Optional, Dict, Any
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
    _extract_columns_from_dataset_response,
)
from .validation import (
    _validate_metric_string_format,
    _validate_metrics_against_dataset,
)
from .resolution import _validate_sankey_params

logger = logging.getLogger(__name__)


async def generate_chart(
    manager: ConnectionManager,
    server_id: str,
    dataset_id: int,
    config: str,
    slice_name: Optional[str] = None,
    description: Optional[str] = None
 ) -> str:
    """
    MCP Tool: superset_generate_chart - Generate a chart from a config dict and dataset.

    Similar to create_chart but takes a config dict (instead of individual params)
    and a dataset_id (instead of datasource_id/type). Performs the same comprehensive
    validation pipeline: viz_type check, metric validation, column validation,
    datasource compatibility, and post-creation data endpoint testing.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        dataset_id: The numeric ID of the dataset to use as the chart's datasource.
        config: JSON string of the chart configuration. Must include 'viz_type' and
            any viz_type-specific fields (metrics, columns, groupby, etc.).
        slice_name: Optional display name for the chart. Defaults to
            "Chart from dataset {dataset_id}" if not provided.
        description: Optional human-readable description of the chart.

    Returns:
        JSON string containing the created chart's details (chart_id, slice_name, url,
            result) on success, or a ChartError JSON with detailed error messages on failure.

    Example:
        result = await generate_chart(
            manager, "default", dataset_id=42,
            config='{"viz_type": "bar", "metrics": ["SUM(sales)"], "groupby": ["region"]}',
            slice_name="Monthly Sales"
        )
        # Returns JSON with chart_id, slice_name, url, and result on success.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_generate_chart", status="error").inc()
        mc.record_error(tool="superset_generate_chart", error_message=f"Server '{server_id}' not found.")
        return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    known_types = await _ensure_chart_types_cached(manager, server_id)

    start_time = time.monotonic()
    try:
        chart_config = json.loads(config) if config else {}

        viz_type = chart_config.get("viz_type", "table")
        actual_viz_type = _resolve_viz_type(viz_type)

        if not _is_known_chart_type(known_types, actual_viz_type):
            mc = get_metrics()
            mc.tool_calls.labels(tool="superset_generate_chart", status="error").inc()
            mc.record_error(tool="superset_generate_chart", error_message=f"Unknown chart type '{actual_viz_type}'")
            return ChartError(
                f"Chart type '{actual_viz_type}' is not recognized.",
                details=f"Please call 'superset_get_all_chart_schemas' first to discover all available chart types. Known types: {', '.join(known_types[:20])}{'...' if len(known_types) > 20 else ''}",
            ).to_json()
        form_data: Dict[str, Any] = {
            "datasource_id": dataset_id,
            "datasource_type": "table",
            "datasource": f"{dataset_id}__table",
        }
        form_data.update(chart_config)
        form_data["viz_type"] = actual_viz_type

        fixed_params = auto_fix_chart_params(actual_viz_type, form_data)

        dataset_columns = []
        dataset_metrics = []
        dataset_fetch_error = None
        try:
            dataset_response = await impl_superset_api(manager, server_id, "GET", f"/api/v1/dataset/{dataset_id}")
            dataset_columns = _extract_columns_from_dataset_response(dataset_response)
            try:
                dataset_data = json.loads(dataset_response)
                dataset_metrics = dataset_data.get("result", {}).get("metrics", [])
            except Exception:
                pass
        except Exception as e:
            dataset_fetch_error = str(e)

        from modules.SupersetModule.superset_validation import NO_METRICS_TYPES
        if dataset_fetch_error and actual_viz_type not in NO_METRICS_TYPES:
            mc = get_metrics()
            mc.tool_calls.labels(tool="superset_generate_chart", status="error").inc()
            mc.record_error(
                tool="superset_generate_chart",
                error_message=f"Dataset schema fetch failed for dataset {dataset_id}"
            )
            return ChartError(
                f"Chart generation blocked: cannot validate columns for dataset {dataset_id}",
                details=(
                    f"Failed to fetch dataset schema for dataset {dataset_id}. "
                    f"Column validation is required before chart generation to prevent "
                    f"broken charts.\n\n"
                    f"Error: {dataset_fetch_error}\n\n"
                    f"Verify that dataset {dataset_id} exists and has columns defined."
                ),
                status_code=400,
            ).to_json()

        if dataset_columns:
            fixed_params, column_warnings = resolve_chart_params(fixed_params, dataset_columns)
            if column_warnings:
                validation_warning = "Column fixes: " + "; ".join(column_warnings)
            else:
                validation_warning = None

            logger.info(f"Running pre-chart data validation for dataset_id={dataset_id}")
            validation_result = validate_chart_data_against_dataset(
                fixed_params, dataset_columns, actual_viz_type
            )

            if not validation_result["is_valid"]:
                logger.warning(
                    f"Chart validation failed for '{slice_name}': "
                    f"{len(validation_result['errors'])} errors, "
                    f"{len(validation_result['missing_columns'])} missing columns"
                )
                error_msg = format_validation_error(validation_result, slice_name, dataset_id)

                mc = get_metrics()
                mc.tool_calls.labels(tool="superset_generate_chart", status="error").inc()
                mc.record_error(
                    tool="superset_generate_chart",
                    error_message=f"Missing columns in dataset: {len(validation_result['missing_columns'])} columns not found"
                )

                return ChartError(
                    error_msg["title"],
                    details=error_msg["body"],
                    status_code=400,
                ).to_json()

            if validation_result.get("warnings"):
                validation_warnings = "; ".join(validation_result["warnings"])
                if validation_warning:
                    validation_warning = validation_warning + " | Validation: " + validation_warnings
                else:
                    validation_warning = "Validation: " + validation_warnings
        else:
            validation_warning = None
            logger.warning(
                f"Could not fetch dataset columns for dataset_id={dataset_id}, "
                f"skipping column validation"
            )

        sankey_warning = _validate_sankey_params(fixed_params, slice_name)
        if sankey_warning:
            return ChartError(
                sankey_warning["title"],
                details=sankey_warning["body"],
                status_code=400,
            ).to_json()

        metric_errors = _validate_metrics_against_dataset(
            fixed_params, dataset_metrics, actual_viz_type, dataset_columns
        )
        if not dataset_columns and not dataset_metrics and not metric_errors:
            metric_errors = _validate_metric_string_format(fixed_params)
        if metric_errors:
            mc = get_metrics()
            mc.tool_calls.labels(tool="superset_generate_chart", status="error").inc()
            mc.record_error(
                tool="superset_generate_chart",
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
            from modules.SupersetModule.superset_validation import validate_datasource_compatibility
            compat_errors = validate_datasource_compatibility(actual_viz_type, fixed_params, dataset_columns)
            if compat_errors:
                mc = get_metrics()
                mc.tool_calls.labels(tool="superset_generate_chart", status="error").inc()
                mc.record_error(
                    tool="superset_generate_chart",
                    error_message=f"Datasource compatibility: {len(compat_errors)} issues"
                )
                return ChartError(
                    f"Chart creation blocked: Datasource incompatible with {actual_viz_type}",
                    details=(
                        f"Chart '{slice_name}' cannot be created — "
                        f"{len(compat_errors)} issue(s):\n\n"
                        + "\n".join(f"  {i+1}. {e}" for i, e in enumerate(compat_errors))
                    ),
                    status_code=400,
                ).to_json()

        errors = validate_chart_params(actual_viz_type, fixed_params)
        if errors:
            mc = get_metrics()
            mc.tool_calls.labels(tool="superset_generate_chart", status="error").inc()
            mc.record_error(
                tool="superset_generate_chart",
                error_message=f"Structural validation failed: {len(errors)} errors"
            )
            return ChartError(
                "Chart creation blocked: Structural validation failed",
                details=(
                    f"Chart '{slice_name}' has {len(errors)} structural issue(s):\n\n"
                    + format_error_summary(errors)
                ),
                status_code=400,
            ).to_json()

        chart_name = slice_name or f"Chart from dataset {dataset_id}"

        if "datasource_id" not in fixed_params or fixed_params["datasource_id"] is None:
            fixed_params["datasource_id"] = dataset_id
        if "datasource" not in fixed_params:
            fixed_params["datasource"] = f"{dataset_id}__table"
        if "datasource_type" not in fixed_params:
            fixed_params["datasource_type"] = "table"

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
            "slice_name": chart_name,
            "datasource_id": dataset_id,
            "datasource_type": "table",
            "viz_type": actual_viz_type,
            "params": json.dumps(fixed_params),
        }
        if description:
            chart_payload["description"] = description

        endpoint = "/api/v1/chart/"
        logger.info(
            "Chart POST: slice_name=%s viz_type=%s dataset_id=%s params=%s",
            chart_name, actual_viz_type, dataset_id,
            json.dumps(fixed_params, indent=2)[:4000],
        )
        resp = await execute_request(ctx, "POST", endpoint, json=chart_payload)
        resp.raise_for_status()
        result = resp.json()
        chart_id = result.get("id") or result.get("result", {}).get("id", 0)

        try:
            result["_mermaid_graph"] = chart_to_mermaid(actual_viz_type, fixed_params, chart_name)
        except Exception:
            result["_mermaid_graph"] = None

        if validation_warning:
            result["_validation_warning"] = validation_warning

        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_generate_chart", status="success").inc()
        mc.tool_duration.labels(tool="superset_generate_chart").observe(time.monotonic() - start_time)
        mc.resources_created.labels(resource_type="chart").inc()
        return json.dumps({
            "saved": True,
            "chart_id": chart_id,
            "slice_name": chart_name,
            "url": f"{ctx.config.base_url.rstrip('/')}/chart/{chart_id}/",
            "result": result
        }, indent=2)

    except json.JSONDecodeError:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_generate_chart", status="error").inc()
        mc.record_error(tool="superset_generate_chart", error_message="'config' is not a valid JSON string.")
        return ChartError("'config' is not a valid JSON string.", details=config).to_json()
    except httpx.HTTPStatusError as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_generate_chart", status="error").inc()
        mc.record_error(tool="superset_generate_chart", error_message=f"HTTP {e.response.status_code} generating chart", status_code=e.response.status_code)
        return ChartError(
            f"HTTP {e.response.status_code} generating chart",
            status_code=e.response.status_code,
            details=e.response.text,
        ).to_json()
    except Exception as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_generate_chart", status="error").inc()
        mc.record_error(tool="superset_generate_chart", error_message=str(e))
        return ChartError(f"Unexpected error generating chart: {e}", details=str(e)).to_json()
