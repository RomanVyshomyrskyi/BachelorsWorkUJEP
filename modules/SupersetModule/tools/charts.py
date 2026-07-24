"""
Chart management tools for Apache Superset MCP integration.

This module provides comprehensive chart CRUD operations, validation,
and metadata discovery for Apache Superset. It handles chart creation
with extensive pre-validation to prevent "columns missing in dataset"
errors, post-creation verification, data endpoint testing, and chart
schema discovery with caching.

MCP Tools Provided:
    - superset_create_chart: Create a new Superset chart with full validation
    - superset_update_chart: Update an existing chart's configuration
    - superset_generate_chart: Generate a chart from a config dict and dataset
    - superset_list_charts: List all charts on a Superset server
    - superset_get_chart_info: Get detailed information about a specific chart
    - superset_get_chart_data: Fetch underlying data for a chart
    - superset_get_chart_preview: Get a visual preview URL for a chart
    - superset_get_chart_type_schema: Get schema for a specific chart type
    - superset_get_all_chart_schemas: Discover ALL chart types with their schemas
    - superset_get_chart_api_info: Get metadata about the chart API
    - superset_get_standard_chart_params: Get standard params for a viz type
    - superset_get_chart_creation_rules: Get expert rules for creating charts
"""

import sys
import json
import logging
import httpx
import time
import os
from typing import Optional, Union, Dict, Any, List
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.exceptions import ChartError
from modules.SupersetModule.schemas.chart import (
    ChartListItem,
    ChartDetail,
    ChartPreviewResponse,
    ChartDataResponse,
    ChartTypeSchema,
 )
from modules.SupersetModule.schemas.common import SupersetListResponse, SupersetDetailResponse
from modules.SupersetModule import rules
from modules.SupersetModule.superset_validation import (
    validate_chart_params,
    auto_fix_chart_params,
    format_error_summary,
 )
from modules.SupersetModule.superset_mermaid import chart_to_mermaid
from modules.SupersetModule.resolver import resolve_chart_params
from modules.SupersetModule.chart_strategies import TYPE_MAP
from modules.metrics import get_metrics
from modules.SupersetModule.tools.chart_validation import (
    validate_chart_data_against_dataset,
    format_validation_error,
)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".cache")
CACHE_FILE = os.path.join(CACHE_DIR, "chart_schemas.json")
CHART_TYPES_CACHE_FILE = os.path.join(CACHE_DIR, "known_chart_types.json")

logger = logging.getLogger(__name__)

_debug_log_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs", "chart_debug.log")
try:
    os.makedirs(os.path.dirname(_debug_log_path), exist_ok=True)
    _debug_handler = logging.FileHandler(_debug_log_path)
    _debug_handler.setLevel(logging.DEBUG)
    _debug_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    ))
    logger.addHandler(_debug_handler)
    logger.info("Chart debug log initialized at %s", _debug_log_path)
except (OSError, PermissionError) as e:
    print(f"WARNING: Could not create chart debug log: {e}", file=sys.stderr)

CACHE_TTL_SECONDS = 86400  # 24 hours


async def _ensure_chart_types_cached(manager: ConnectionManager, server_id: str) -> List[str]:
    """
    Ensure chart types cache exists and is fresh.
    Returns list of known chart type names.
    Auto-fetches if cache is missing or expired.
    """
    import asyncio

    # Check cache
    if os.path.isfile(CHART_TYPES_CACHE_FILE):
        try:
            file_age = time.time() - os.path.getmtime(CHART_TYPES_CACHE_FILE)
            if file_age < CACHE_TTL_SECONDS:
                with open(CHART_TYPES_CACHE_FILE, "r") as f:
                    cached = json.load(f)
                return [t for t in cached.get("chart_types", []) if t != "parallel"]
        except (json.JSONDecodeError, OSError):
            pass

    # Fetch from Superset API
    try:
        info_raw = await impl_superset_api(manager, server_id, "GET", "/api/v1/chart/_info")
        info_data = json.loads(info_raw)
    except Exception:
        # Fallback to local TYPE_MAP
        return list(TYPE_MAP.values())

    # Extract chart types from _info
    chart_types = []
    properties = info_data.get("result", {}).get("properties", {})

    if isinstance(properties, dict):
        # Check form_data.properties.viz_type.enum
        fd = properties.get("form_data", {})
        if isinstance(fd, dict):
            fd_props = fd.get("properties", {})
            viz_type = fd_props.get("viz_type", {})
            if isinstance(viz_type, dict):
                enum_vals = viz_type.get("enum", [])
                if enum_vals:
                    chart_types = [str(v) for v in enum_vals]

        if not chart_types:
            form_data_prop = properties.get("form_data", {})
            if isinstance(form_data_prop, dict):
                fd_viz = form_data_prop.get("viz_type", {})
                if isinstance(fd_viz, dict):
                    enum_vals = fd_viz.get("enum", [])
                    if enum_vals:
                        chart_types = [str(v) for v in enum_vals]

        if not chart_types:
            ct = properties.get("chart_types", [])
            if isinstance(ct, list) and ct:
                chart_types = [str(c) for c in ct]

        if not chart_types:
            for key, val in properties.items():
                if isinstance(val, dict) and "enum" in val:
                    enum_vals = val.get("enum", [])
                    if isinstance(enum_vals, list) and len(enum_vals) > 2:
                        chart_types = [str(v) for v in enum_vals]
                        break

    if not chart_types:
        chart_types = list(TYPE_MAP.values())

    # Filter out chart types not registered on this Superset instance
    CHART_TYPES_BLOCKED = {"parallel"}
    chart_types = [t for t in chart_types if t not in CHART_TYPES_BLOCKED]

    # Save cache
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CHART_TYPES_CACHE_FILE, "w") as f:
            json.dump({
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                "chart_types": chart_types,
            }, f, indent=2)
    except OSError:
        pass

    return chart_types


def _is_known_chart_type(chart_types: List[str], viz_type: str) -> bool:
    """Check if a viz_type is known (either in dynamic cache or local TYPE_MAP)."""
    if viz_type in chart_types:
        return True
    # Also check against local TYPE_MAP values as fallback
    return viz_type in TYPE_MAP.values()


async def get_chart_api_info(manager: ConnectionManager, server_id: str) -> str:
    """
    MCP Tool: superset_get_chart_api_info - Retrieves metadata about the chart API.

    Fetches the chart API's _info endpoint which contains metadata about
    supported chart types, available filters, permissions, and API properties.
    Useful for understanding what chart types and features are available
    on a specific Superset instance.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server to query.

    Returns:
        JSON string containing the chart API metadata from /api/v1/chart/_info,
        including supported viz_types, form_data schemas, and feature flags.
    """
    # Delegate to the generic Superset API helper for the GET request
    return await impl_superset_api(manager, server_id, "GET", "/api/v1/chart/_info")


def _resolve_viz_type(viz_type: str) -> str:
    """
    Resolve a generic/human-friendly viz_type alias to the actual Superset viz_type string.

    Maps common shorthand names (e.g., 'bar', 'line', 'table') to their full
    Superset equivalents (e.g., 'echarts_bar', 'echarts_timeseries_line', 'table').
    This allows users to specify chart types using familiar names.

    Args:
        viz_type: A chart type name, which may be a shorthand alias
            (e.g., 'bar', 'line', 'pie', 'table', 'scatter') or a full
            Superset viz_type string.

    Returns:
        The resolved Superset viz_type string. If the input is not a known
        alias, returns the input unchanged (pass-through for full viz_types).
    """
    # Look up the type in the TYPE_MAP alias dictionary, fall back to original input
    return TYPE_MAP.get(viz_type, viz_type)


def _extract_columns_from_dataset_response(response_str: str) -> List[Dict[str, Any]]:
    """
    Extract the columns list from a JSON-encoded Superset dataset API response.

    Parses the response body from GET /api/v1/dataset/{id} and returns the
    'columns' array, which contains column metadata (name, type, etc.)
    for use in chart validation.

    Args:
        response_str: Raw JSON string response from the Superset dataset API.
            Expected format: {"result": {"columns": [...], "metrics": [...]}}

    Returns:
        List of column dicts from the dataset response. Returns empty list
        if parsing fails or no columns are found.
    """
    # Attempt to parse the JSON response and extract the columns array
    try:
        data = json.loads(response_str)
        result = data.get("result", {})
        if isinstance(result, dict):
            columns = result.get("columns", [])
            if isinstance(columns, list):
                return columns
        return []
    # Return empty list on any parse error to avoid crashing the caller
    except (json.JSONDecodeError, TypeError):
        return []

def _validate_metric_string_format(params: Dict[str, Any]) -> List[str]:
    """
    Basic syntax validation for metric strings.

    Runs when no dataset schema is available for column-level validation.
    Catches obviously wrong metric strings by parsing their format against
    the expected AGGREGATION(column_name) pattern.

    Args:
        params: Chart params dict containing 'metric', 'metrics', 'entity',
            'orderby', and/or 'timeseries_limit_metric' fields.

    Returns:
        List of error strings. Empty list means all metric strings have
        valid syntax (though not necessarily correct column references).
    """
    import re
    errors: List[str] = []

    # Helper: validate a single metric string against the AGGREGATION(column_name) format
    def check_metric_string(ms: str, label: str) -> None:
        """Validate a single metric string has the expected AGG(col) format.

        Args:
            ms: The metric string to validate (e.g. "SUM(sales)").
            label: Context label for error messages (e.g. "'metric'").

        Returns:
            None — appends error descriptions to the outer ``errors`` list.
        """
        s = ms.strip()
        if not s:
            errors.append(f"Empty metric string in {label}")
            return
        s_lower = s.lower()
        if s_lower == "count":
            return  # built-in count is always valid — skip regex check
        match = re.match(r"^(SUM|AVG|MIN|MAX|COUNT|COUNT_DISTINCT)\s*\(\s*.+?\s*\)$", s, re.IGNORECASE)
        if not match:
            errors.append(
                f"'{s}' in {label} has invalid format. "
                f"Expected 'count' or 'AGGREGATION(column_name)' "
                f"(e.g., 'SUM(sales)', 'AVG(price)')."
            )
    
    # Step 1: Validate the singular 'metric' field — can be string, dict, or None
    if "metric" in params:
        m = params["metric"]
        if m is None:
            errors.append("'metric' is null — set it to 'count' or 'SUM(column_name)'")
        elif isinstance(m, str):
            check_metric_string(m, "'metric'")
        elif isinstance(m, dict):
            col_name = m.get("column", {}).get("column_name")
            if not col_name:
                errors.append("'metric' object has null or missing column_name")

    # Step 2: Validate the 'metrics' array (plural) — each element is checked individually
    if "metrics" in params and params["metrics"]:
        for i, m in enumerate(params["metrics"]):
            if isinstance(m, str):
                check_metric_string(m, f"'metrics[{i}]'")
            elif isinstance(m, dict):
                col_name = m.get("column", {}).get("column_name")
                if not col_name:
                    errors.append(f"'metrics[{i}]' object has null or missing column_name")

    # Step 3: Check 'entity' — null/empty entity for map types causes crashes
    if "entity" in params and not params["entity"]:
        errors.append("'entity' is null or empty — set it to a valid column name (e.g., 'country_code')")

    # Step 4: Check 'orderby' — format: [["col", true], ...] or [{"column": {"column_name": "x"}, "asc": true}, ...]
    if "orderby" in params and params["orderby"]:
        orderby = params["orderby"]
        if isinstance(orderby, list):
            for i, entry in enumerate(orderby):
                if isinstance(entry, list):
                    if len(entry) >= 1 and entry[0] is None:
                        errors.append(f"'orderby[{i}]' has null column reference")
                elif isinstance(entry, dict):
                    col_entry = entry.get("column", {})
                    col_name = col_entry.get("column_name") if isinstance(col_entry, dict) else None
                    if col_name is None:
                        errors.append(f"'orderby[{i}]' has null or missing column reference")

    # Step 5: Check 'timeseries_limit_metric' — can be string, dict, or None
    if "timeseries_limit_metric" in params:
        tlm = params["timeseries_limit_metric"]
        if tlm is None:
            errors.append("'timeseries_limit_metric' is null — remove it or set to a valid metric")
        elif isinstance(tlm, dict):
            col_name = tlm.get("column", {}).get("column_name")
            if col_name is None:
                errors.append("'timeseries_limit_metric' object has null column_name")

    return errors


NUMERIC_TYPES = {
    "int", "int2", "int4", "int8", "int16", "int32", "int64",
    "integer", "smallint", "bigint", "tinyint",
    "float", "float4", "float8", "double", "double precision",
    "decimal", "numeric", "number", "real",
    "money",
}


def _validate_metrics_against_dataset(
    params: Dict[str, Any],
    dataset_metrics: List[Dict[str, Any]],
    viz_type: str,
    dataset_columns: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    """
    Validate that all metrics used in chart params exist in the dataset.

    When dataset_metrics is empty (common for physical tables), falls back
    to checking that columns referenced in string metrics (e.g., 'SUM(sales)')
    actually exist in dataset_columns and have compatible types.

    Args:
        params: Chart params dict containing metric references.
        dataset_metrics: List of predefined metric dicts from the dataset API.
        viz_type: The chart visualization type (used for context).
        dataset_columns: Optional list of column dicts for fallback validation.

    Returns:
        List of missing/invalid metric descriptions. Empty list = all valid.
    """
    import re
    missing_metrics: List[str] = []
    dataset_metric_names = {m["metric_name"] for m in dataset_metrics}

    # Step 1: Build column lookup for type checking on fallback validation
    column_map: Dict[str, Dict[str, Any]] = {}
    if dataset_columns:
        for col in dataset_columns:
            col_name = col.get("column_name", "")
            if col_name:
                column_map[col_name.lower()] = col
    
    def extract_metric_strings(p: Dict[str, Any]) -> List[str]:
        """Extract all metric strings from chart params.

        Examines both singular ``metric`` and plural ``metrics`` fields,
        converting AdHocMetricObject dicts to ``AGG(col)`` format.

        Args:
            p: Chart params dict containing metric references.

        Returns:
            List of metric strings in ``AGG(col)`` or ``count`` format.
        """
        metrics = []
        
        # Check 'metric' (singular)
        if "metric" in p and p["metric"]:
            metric_val = p["metric"]
            if isinstance(metric_val, str):
                metrics.append(metric_val)
            elif isinstance(metric_val, dict):
                col_name = metric_val.get("column", {}).get("column_name", "")
                if col_name:
                    agg = metric_val.get("aggregate", "AVG")
                    metrics.append(f"{agg}({col_name})")
        
        # Check 'metrics' (plural array)
        if "metrics" in p and p["metrics"]:
            for m in p["metrics"]:
                if isinstance(m, str):
                    metrics.append(m)
                elif isinstance(m, dict):
                    col_name = m.get("column", {}).get("column_name", "")
                    if col_name:
                        agg = m.get("aggregate", "AVG")
                        metrics.append(f"{agg}({col_name})")
        
        return metrics
    
    def parse_metric_string(metric_str: str) -> tuple:
        """Decompose a metric string into (aggregate, column_name).

        Args:
            metric_str: Metric string like ``"SUM(sales)"`` or ``"count"``.

        Returns:
            Tuple of (aggregate, column_name) — both lowercase.
            For ``"count"`` returns ``("count", "count")``.
            For unrecognized patterns returns ``("", metric_str)``.
        """
        s = metric_str.strip().lower()
        if s == "count":
            return ("count", "count")
        m = re.match(r"^(sum|avg|min|max|count|count_distinct)\s*\(\s*(.+?)\s*\)$", s)
        if m:
            return (m.group(1), m.group(2).strip())
        return ("", s)
    
    def normalize_metric(metric_str: str) -> str:
        """Lowercase and strip a metric string for case-insensitive comparison.

        Args:
            metric_str: Raw metric string.

        Returns:
            Normalized metric string (lowercase, stripped).
        """
        metric_str = metric_str.strip()
        if metric_str.lower() == "count":
            return "count"
        return metric_str.lower()
    
    def metric_matches(metric_name: str, target: str) -> bool:
        """Check if a dataset-defined metric matches a target metric string.

        Compares case-insensitively and also handles SQL-style format
        like ``sum__revenue`` matching ``SUM(revenue)``.

        Args:
            metric_name: The metric name from the dataset definition.
            target: The target metric string to match against.

        Returns:
            True if the metrics match, False otherwise.
        """
        name_lower = metric_name.lower()
        target_lower = target.lower()
        
        # Exact match (case-insensitive)
        if name_lower == target_lower:
            return True
        
        # Check SQL-style: "sum__num" matches "SUM(num)"
        if "__" in name_lower:
            parts = name_lower.split("__", 1)
            agg = parts[0]
            col = parts[1]
            match = re.match(r"^(\w+)\s*\(\s*(.+?)\s*\)$", target)
            if match and match.group(1).lower() == agg and match.group(2).lower() == col:
                return True
        
        return False
    
    def column_has_compatible_type(col_name: str, aggregate: str) -> Optional[str]:
        """Verify a column's data type is compatible with an aggregate function.

        Args:
            col_name: The column name to check.
            aggregate: The aggregation function (SUM, AVG, MIN, MAX).

        Returns:
            Error message string if the column type is incompatible
            (e.g., SUM on a text column), or None if compatible.
        """
        col_info = column_map.get(col_name.lower())
        if not col_info:
            return None  # column not in our map, can't check
        
        col_type = str(col_info.get("type", "")).lower()
        if not col_type:
            return None  # no type info, can't check
        
        # Only SUM, AVG, MIN, MAX need numeric types
        if aggregate.lower() not in ("sum", "avg", "min", "max"):
            return None
        
        # Special: "count" is not really a column type check
        if col_name.lower() == "count" and aggregate.lower() in ("count",):
            return None
        
        is_numeric = any(t in col_type for t in NUMERIC_TYPES)
        if not is_numeric:
            return (
                f"Aggregation '{aggregate}()' on column '{col_info['column_name']}' "
                f"(type: {col_type}) will fail — '{aggregate}()' requires a numeric column. "
                f"Use 'count' for row counts or pick a numeric column."
            )
        return None
    
    # Extract all metrics from params
    param_metrics = extract_metric_strings(params)

    for pm in param_metrics:
        normalized = normalize_metric(pm)

        # Step 3: Reject COUNT(count) — user likely meant bare "count"
        # Bare "count" (no parens) is the built-in row count and should NOT be rejected.
        if "(" in pm and ")" in pm:
            parse_result = parse_metric_string(pm)
            agg, col_in_metric = parse_result
            if agg in ("count", "count_distinct") and col_in_metric == "count":
                stripped = agg.replace("_distinct", "").replace("_", "").replace("distinct", "")
                missing_metrics.append(
                    f"'{pm}': use '{stripped}' (bare, without parentheses) instead. "
                    f"'{pm}' tries to aggregate a literal column called 'count', "
                    f"not count rows. Replace with '{stripped}'."
                )
                continue
            # For other parenthesized formulas like 'SUM(sales)', skip the
            # saved-metric lookup below (they're ad-hoc, not saved metrics).
            # Still run column-fallback validation (check if referenced column
            # exists and has compatible type).
            is_ad_hoc = True
        else:
            is_ad_hoc = False
        
        # Parse for column fallback
        parse_result = parse_metric_string(pm)
        agg, col_in_metric = parse_result

        # Step 4: Built-in count — always valid if dataset exists
        if normalized == "count":
            if dataset_metric_names and not any(m.lower().startswith("count") for m in dataset_metric_names):
                missing_metrics.append(
                    f"'{pm}': 'count' is a built-in metric but no count-like metric was "
                    f"found in the dataset's defined metrics."
                )
            continue
        
        # Step 5: Check if metric exists in predefined dataset metrics.
        # Skip for ad-hoc formulas (e.g., 'SUM(sales)') — they're expressions,
        # not saved metric names.
        if dataset_metric_names and not is_ad_hoc:
            found = False
            for dm in dataset_metric_names:
                if metric_matches(dm, pm):
                    found = True
                    break
            if found:
                continue  # matched a predefined metric
        
        # Step 6: Metric not in predefined list — try column fallback
        if col_in_metric and column_map:
            if col_in_metric in column_map:
                # Column exists — check type compatibility
                type_error = column_has_compatible_type(col_in_metric, agg)
                if type_error:
                    missing_metrics.append(type_error)
                continue
            else:
                # Column doesn't exist in dataset
                available = [c.get("column_name", "") for c in dataset_columns] if dataset_columns else []
                suggestion = ""
                # Case-insensitive search for suggestions
                for avail in available:
                    if avail.lower() == col_in_metric:
                        suggestion = f" Did you mean '{avail}' (case mismatch)?"
                        break
                if not suggestion:
                    # Check if there's a close match
                    from difflib import get_close_matches
                    matches = get_close_matches(col_in_metric, [c.lower() for c in available], n=1, cutoff=0.6)
                    if matches:
                        # Find original case
                        for avail in available:
                            if avail.lower() == matches[0]:
                                suggestion = f" Did you mean '{avail}'?"
                                break
        
                missing_metrics.append(
                    f"'{pm}': column '{col_in_metric}' does not exist in this dataset."
                    + suggestion
                    + (f"\nAvailable columns: {', '.join(available[:15])}" if available else "")
                )
                continue
        
        # Step 7: No dataset_metrics and no dataset_columns — can't validate, BLOCK
        if not dataset_metric_names and not column_map:
            available = [c.get("column_name", "") for c in dataset_columns] if dataset_columns else []
            missing_metrics.append(
                f"'{pm}' cannot be validated because no dataset schema was retrieved. "
                f"Dataset returned no columns and no predefined metrics. "
                f"Verify the datasource exists and has columns defined."
            )
            continue
        
        # Step 8: If we got here and have metrics, mark as missing.
        # Skip for ad-hoc formulas — they're not meant to be saved metrics.
        if dataset_metric_names and not is_ad_hoc:
            missing_metrics.append(
                f"'{pm}' does not match any predefined metric in the dataset."
            )
    
    return missing_metrics

def _extract_chart_ids_from_position_json(position_json: str) -> List[int]:
    """
    Extract all chart IDs from a position JSON string.

    Recursively walks the position_json structure to find all nodes
    containing a ``slice_id`` key (the legacy Superset format for
    embedding chart references within dashboard layout trees).

    Args:
        position_json: Raw JSON string of the dashboard position layout.

    Returns:
        List of integer chart (slice) IDs found in the layout.
    """
    chart_ids = []
    try:
        # Normalize input to dict form (accepts both str and dict)
        if isinstance(position_json, str):
            pos = json.loads(position_json)
        else:
            pos = position_json

        def walk(obj):
            """Recursively traverse dicts/lists to find slice_id entries.

            Args:
                obj: A dict or list to traverse.
            """
            if isinstance(obj, dict):
                if "slice_id" in obj and isinstance(obj["slice_id"], int):
                    chart_ids.append(obj["slice_id"])
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)
        
        walk(pos)
    except (json.JSONDecodeError, TypeError):
        pass

    return chart_ids

def _validate_sankey_params(params: Dict[str, Any], slice_name: str) -> Optional[Dict[str, str]]:
    """
    Validate Sankey chart params and return warning if potential cycle detected.

    Sankey charts require a DAG (directed acyclic graph). If source/target
    columns have circular references, Superset will error at render time.
    We validate params structure and suggest the cycle-breaking SQL fix.

    Args:
        params: Chart params dict containing Sankey-specific fields
            ('source', 'target') and viz_type='sankey_v2'.
        slice_name: Name of the chart (used in warning title).

    Returns:
        Dict with 'title' and 'body' keys if warnings/errors found, or None
        if the params are valid (or are not for a Sankey chart).
    """
    # Step 1: Only apply to sankey_v2 charts — skip other viz types silently
    if "sankey_v2" not in params.get("viz_type", ""):
        return None

    errors = []

    # Step 2: Run structural validation via the shared validation module
    from modules.SupersetModule.superset_validation import validate_chart_params
    validation_errors = validate_chart_params("sankey_v2", params)
    if validation_errors:
        errors.extend(validation_errors)

    if errors:
        return {"title": f"Chart '{slice_name}' - Sankey validation errors",
                "body": "\n".join(errors) + "\n\nSankey charts require 'source' and 'target' fields."}

    # Step 3: Check if cycle fix has already been suggested (avoid duplicate warnings)
    if params.get("_cycle_fix_suggested"):
        return None

    # Step 4: Provide helpful cycle fix suggestion — Sankey requires a DAG,
    #         and circular source/target relationships cause render errors.
    source_col = params.get("source", "unknown")
    target_col = params.get("target", "unknown")
    
    return {
        "title": f"Chart '{slice_name}' - Sankey cycle fix needed",
        "body": (
            f"Sankey chart uses source='{source_col}', target='{target_col}'.\n\n"
            f"To prevent 'Sankey is a DAG, the original data has cycle!' errors, "
            f"add this to your dataset SQL:\n\n"
            f"HAVING {source_col} <> {target_col} AND {source_col} < {target_col}\n\n"
            f"This ensures lexicographic ordering breaks all graph cycles."
        )
    }

async def _test_chart_data_endpoint(
    manager: ConnectionManager,
    server_id: str,
    chart_id: int
) -> Dict[str, Any]:
    """
    Test a chart's data endpoint to verify it returns valid data without errors.

    Calls GET /api/v1/chart/{id}/data/ and checks multiple indicators of
    chart health. This is used both pre-creation (via chart validation)
    and post-creation to verify charts actually render.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_id: The numeric ID of the chart to test.

    Returns:
        Dict with keys:
          - is_valid (bool): True if chart data endpoint is healthy
          - error (str|None): Error message if invalid, None if valid
          - row_count (int|None): Number of rows returned by the chart query
    """
    # Step 1: Retrieve the server context to access the Superset API client
    ctx = manager.get_context(server_id)
    if not ctx:
        return {"is_valid": False, "error": "Server context not found", "row_count": None}

    try:
        # Step 2: Execute the GET request to the chart's data endpoint
        resp = await execute_request(ctx, "GET", f"/api/v1/chart/{chart_id}/data/")

        # Step 3: Check if the HTTP response was successful
        if resp.status_code != 200:
            logger.warning(
                "Chart %s data endpoint HTTP %s body=%s",
                chart_id, resp.status_code, str(resp.text)[:1000],
            )
            return {"is_valid": False, "error": f"HTTP {resp.status_code}: {resp.text[:300]}", "row_count": None}

        # Step 4: Parse JSON response and extract key fields for validation
        data = resp.json()
        result = data.get("result", {})
        error = result.get("error")
        status = result.get("status", "unknown")
        row_count = result.get("sql_rowcount")

        # Step 5: Check for explicit error field in the API response
        if error:
            logger.warning("Chart %s data endpoint error field: %s", chart_id, str(error)[:500])
            return {"is_valid": False, "error": f"Data endpoint error: {error}", "row_count": row_count}

        # Step 6: Check if the query execution status is successful
        if status != "success":
            return {"is_valid": False, "error": f"Data endpoint status: {status}", "row_count": row_count}

        # Step 7: A chart returning zero rows is considered broken
        if not row_count or row_count == 0:
            return {"is_valid": False, "error": "Chart returned no data rows (sql_rowcount=0)", "row_count": 0}

        # Step 8: Scan the FULL response text for common error keywords that might indicate
        #         issues not caught by explicit status checks
        resp_lower = str(resp.text).lower()
        error_keywords = ["does not exist", "doesn't exist", "cannot compile", "undefined",
                          "db engine error", "data error", "error:", "exception:",
                          "traceback", "may not be null", "field may not be",
                          "not found", "is null", "noneType", "can't access",
                          "duplicate", "not subscriptable", "is not defined",
                          "is undefined", "label", "datetime column not provided",
                          "not provided as part", "rendering the visualization"]
        matches = [kw for kw in error_keywords if kw in resp_lower]
        if matches:
            logger.warning(
                "Chart %s data endpoint errors: keywords=%s raw=%s",
                chart_id, matches, str(resp.text)[:1000],
            )
            return {"is_valid": False, "error": f"Chart response contains error keywords: {matches}", "row_count": row_count}

        # Step 9: All checks passed — chart data endpoint is healthy
        return {"is_valid": True, "error": None, "row_count": row_count}

    # Handle HTTP-level errors (e.g., 404, 403, 500)
    except httpx.HTTPStatusError as e:
        return {"is_valid": False, "error": f"HTTP {e.response.status_code}: {e.response.text[:300]}", "row_count": None}
    # Catch-all for unexpected exceptions during the request
    except Exception as e:
        return {"is_valid": False, "error": f"Data endpoint exception: {str(e)[:300]}", "row_count": None}

async def _delete_chart(
    manager: ConnectionManager,
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
    # Step 1: Retrieve server context for the API request
    ctx = manager.get_context(server_id)
    if not ctx:
        return False

    try:
        # Step 2: Send DELETE request to the chart API endpoint
        resp = await execute_request(ctx, "DELETE", f"/api/v1/chart/{chart_id}")
        # Accept both 200 (OK with body) and 204 (No Content) as success
        return resp.status_code in [200, 204]
    except Exception:
        return False


async def _validate_chart_on_datasource(
    manager: ConnectionManager,
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
    # Step 1: Retrieve server context for the API request
    ctx = manager.get_context(server_id)
    if not ctx:
        return {"chart_id": chart_id, "is_valid": False, "error": "Server not found"}

    try:
        # Step 2: Fetch the chart metadata to get viz_type, params, and datasource_id
        resp = await execute_request(ctx, "GET", f"/api/v1/chart/{chart_id}")
        chart = resp.json().get("result", {})
        viz_type = chart.get("viz_type", "unknown")
        params_str = chart.get("params", "{}")

        # Step 3: Parse the JSON-serialized params into a dict
        try:
            params = json.loads(params_str)
        except json.JSONDecodeError:
            params = {}

        dataset_id = chart.get("datasource_id")

        # Step 4: Fetch the dataset's column definitions for compatibility checking
        try:
            ds_resp = await execute_request(ctx, "GET", f"/api/v1/dataset/{dataset_id}")
            ds = ds_resp.json().get("result", {})
            columns = ds.get("columns", [])
        except Exception:
            columns = []

        # Step 5: Run datasource compatibility validation using the validation module
        from modules.SupersetModule.superset_validation import (
            validate_datasource_compatibility,
        )
        compat_errors = validate_datasource_compatibility(viz_type, params, columns)

        # Step 6: If compatibility check fails, return early with errors
        if compat_errors:
            return {
                "chart_id": chart_id,
                "is_valid": False,
                "error": "Compatibility: " + "; ".join(compat_errors),
                "viz_type": viz_type,
            }

        # Step 7: Test the chart's data endpoint to ensure it actually returns data
        data_result = await _test_chart_data_endpoint(manager, server_id, chart_id)

        # Step 8: If data endpoint test fails, return the failure details
        if not data_result["is_valid"]:
            return {
                "chart_id": chart_id,
                "is_valid": False,
                "error": f"Data test failed: {data_result['error']}",
                "viz_type": viz_type,
            }

        # Step 9: All validations passed — return success result
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
    manager: ConnectionManager,
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
    # Step 1: Retrieve server context for the API request
    ctx = manager.get_context(server_id)
    if not ctx:
        return ["Server context not found"]

    try:
        # Step 2: Fetch the chart to inspect its saved params
        resp = await execute_request(ctx, "GET", f"/api/v1/chart/{chart_id}")
        chart = resp.json().get("result", {})
        params_str = chart.get("params", "{}")

        # Step 3: Parse the JSON-serialized params; fail immediately if not valid JSON
        try:
            params = json.loads(params_str)
        except (json.JSONDecodeError, TypeError):
            return [f"Chart params is not valid JSON: {params_str[:100]}"]

        errors: List[str] = []

        # Step 4: Check the 'metric' field (singular) — must not be null or have null column_name
        if "metric" in params:
            m = params["metric"]
            if m is None:
                errors.append("saved 'metric' is null")
            elif isinstance(m, dict):
                col_name = m.get("column", {}).get("column_name")
                if col_name is None:
                    errors.append("saved 'metric' has null column_name")
        
        # Step 5: Check the 'metrics' field (plural array) — each element must not be null
        if "metrics" in params and isinstance(params["metrics"], list):
            for i, m in enumerate(params["metrics"]):
                if m is None:
                    errors.append(f"saved 'metrics[{i}]' is null")
                elif isinstance(m, dict):
                    col_name = m.get("column", {}).get("column_name")
                    if col_name is None:
                        errors.append(f"saved 'metrics[{i}]' has null column_name")
        
        # Step 6: Check 'orderby' — array of column references, each must have valid column
        if "orderby" in params and isinstance(params["orderby"], list):
            for i, entry in enumerate(params["orderby"]):
                if isinstance(entry, list) and len(entry) >= 1 and entry[0] is None:
                    errors.append(f"saved 'orderby[{i}]' has null column reference")
                elif isinstance(entry, dict):
                    col_entry = entry.get("column", {})
                    if isinstance(col_entry, dict) and col_entry.get("column_name") is None:
                        errors.append(f"saved 'orderby[{i}]' has null column_name")
        
        # Step 7: Check 'timeseries_limit_metric' — must not be null
        if "timeseries_limit_metric" in params and params["timeseries_limit_metric"] is None:
            errors.append("saved 'timeseries_limit_metric' is null")
        
        # Step 8: Check 'entity' — required for graph/map charts, must not be empty
        if "entity" in params and not params["entity"]:
            errors.append("saved 'entity' is null or empty")
        
        # Step 9: Check 'columns' array (sunburst, treemap, boxplot, etc.) — no null/empty entries
        if "columns" in params and isinstance(params["columns"], list):
            for i, col in enumerate(params["columns"]):
                if col is None:
                    errors.append(f"saved 'columns[{i}]' is null")
                elif isinstance(col, str) and not col.strip():
                    errors.append(f"saved 'columns[{i}]' is empty")
        
        # Step 10: Check 'all_columns' array (table chart) — no null/empty entries
        if "all_columns" in params and isinstance(params["all_columns"], list):
            for i, col in enumerate(params["all_columns"]):
                if col is None:
                    errors.append(f"saved 'all_columns[{i}]' is null")
                elif isinstance(col, str) and not col.strip():
                    errors.append(f"saved 'all_columns[{i}]' is empty")
        
        # Step 11: Check 'groupby' array — no null/empty entries
        if "groupby" in params and isinstance(params["groupby"], list):
            for i, col in enumerate(params["groupby"]):
                if col is None:
                    errors.append(f"saved 'groupby[{i}]' is null")
                elif isinstance(col, str) and not col.strip():
                    errors.append(f"saved 'groupby[{i}]' is empty")
        
        # Step 12: Check time-based chart types require a temporal column reference
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


async def create_chart(
    manager: ConnectionManager,
    server_id: str,
    slice_name: str,
    viz_type: str,
    datasource_id: int,
    datasource_type: str,
    params: str,
    description: Optional[str] = None
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
    """
    # Step 1: Retrieve the server context for API access
    ctx = manager.get_context(server_id)
    if not ctx:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_create_chart", status="error").inc()
        mc.record_error(tool="superset_create_chart", error_message=f"Server '{server_id}' not found.")
        return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    # Step 2: Ensure chart types cache is available for validation
    known_types = await _ensure_chart_types_cached(manager, server_id)

    start_time = time.monotonic()
    try:
        # Step 3: Resolve shorthand viz_type (e.g., 'bar') to full Superset type (e.g., 'echarts_bar')
        actual_viz_type = _resolve_viz_type(viz_type)

        # Step 4: Validate viz_type against known chart types
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

        # Step 5: Fetch dataset schema for column and metric validation
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

        # Step 5b: Block if dataset schema fetch failed (exception, not just empty data)
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

        # Step 6: ── Metric validation (always runs, even when columns/metrics are empty) ──
        # When dataset_columns is empty, we can't check column existence, but we
        # still validate metric string format and run the post-creation data test.
        metric_errors = _validate_metrics_against_dataset(
            fixed_params, dataset_metrics, actual_viz_type, dataset_columns
        )
        
        # Step 7: Even without schema data, validate metric string format (syntax check)
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

        # Step 8: ── Column-level validation (only when dataset columns are available) ──
        if dataset_columns:
            # Step 8a: Auto-fix column name typos and resolve column references
            fixed_params, column_warnings = resolve_chart_params(fixed_params, dataset_columns)
            if column_warnings:
                warning = "Column name fixes: " + "; ".join(column_warnings)
            else:
                warning = None
            
            # Step 8b: Validate Sankey charts — errors and cycle warnings both block creation
            sankey_warning = _validate_sankey_params(fixed_params, slice_name)
            if sankey_warning:
                return ChartError(
                    sankey_warning["title"],
                    details=sankey_warning["body"],
                    status_code=400,
                ).to_json()
            
            # Step 8c: Validate chart data against dataset BEFORE creating
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
            
            # Step 8d: Merge validation warnings into the warning string
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
        
        # Step 9: Validate datasource compatibility for known viz types
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

        # Step 10: Run structural chart param validation against chart type schema
        errors = validate_chart_params(actual_viz_type, fixed_params)
        validation_errors = format_error_summary(errors) if errors else None
        
        if validation_errors:
            if warning:
                warning = warning + " | " + validation_errors
            else:
                warning = "Validation: " + validation_errors

        # Step 11: Ensure datasource_id is in params (required by Superset frontend)
        if "datasource_id" not in fixed_params or fixed_params["datasource_id"] is None:
            fixed_params["datasource_id"] = datasource_id
        # Ensure datasource field is set
        if "datasource" not in fixed_params:
            fixed_params["datasource"] = f"{datasource_id}__table"
        # Ensure datasource_type is set
        if "datasource_type" not in fixed_params:
            fixed_params["datasource_type"] = datasource_type

        chart_payload = {
            "slice_name": slice_name,
            "description": description,
            "viz_type": actual_viz_type,
            "datasource_id": datasource_id,
            "datasource_type": datasource_type,
            "params": json.dumps(fixed_params),
        }

        # Step 12: Send POST request to Superset API to create the chart
        endpoint = "/api/v1/chart/"
        resp = await execute_request(ctx, "POST", endpoint, json=chart_payload)
        resp.raise_for_status()
        result = resp.json()

        # Step 13: Post-creation — verify saved params have no null/empty values
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
        
        # Step 14: Post-creation — test chart data endpoint to verify it renders
        data_test = await _test_chart_data_endpoint(manager, server_id, chart_id)

        if not data_test["is_valid"]:
            # Chart created but fails data endpoint — delete it and return error
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

async def update_chart(
    manager: ConnectionManager,
    server_id: str,
    chart_id: int,
    json_body: str
) -> str:
    """
    MCP Tool: superset_update_chart - Update an existing chart's configuration.

    Sends a PUT request to the Superset chart API to modify a chart's settings
    such as name, params, description, or other properties.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_id: The numeric ID of the chart to update.
        json_body: JSON string containing the fields to update. See Superset API
            docs for the chart model structure. Only the fields included in this
            JSON will be modified.

    Returns:
        JSON string containing the updated chart's details from the API response,
        or an error JSON if the update fails.
    """
    # Delegate to the generic Superset API helper for the PUT request
    return await impl_superset_api(manager, server_id, "PUT", f"/api/v1/chart/{chart_id}", json_body=json_body)


def get_standard_chart_params(viz_type: str, datasource_id: int, overrides_json: Optional[str] = None) -> str:
    """
    MCP Tool: superset_get_standard_chart_params - Get standard params for a viz type.

    Returns a JSON object with sensible default parameters for the given visualization
    type and datasource. These defaults include required fields and typical values
    that work with most datasets. Use this as a starting point when building chart
    configuration, then customize as needed.

    Args:
        viz_type: The chart visualization type (e.g., 'echarts_bar', 'echarts_line',
            'table', 'pivot_table', 'time_table').
        datasource_id: The ID of the dataset to use. Used to populate dataset-specific
            defaults like available metrics and column references.
        overrides_json: Optional JSON string of parameter overrides that replace
            the default values. Use this to set specific values while keeping
            the rest of the defaults.

    Returns:
        JSON string of the standard parameters for the given viz_type and datasource.
        This can be used as the base for chart creation or exploration.
    """
    # Step 1: Parse override JSON if provided, otherwise use empty dict
    overrides = json.loads(overrides_json) if overrides_json else {}
    # Step 2: Get base params from rules module, applying user overrides on top
    params = rules.get_standard_chart_params(viz_type, datasource_id, **overrides)
    return json.dumps(params, indent=2)


def get_chart_creation_rules() -> str:
    """
    MCP Tool: superset_get_chart_creation_rules - Get expert rules for creating charts.

    Returns a set of expert guidelines and best practices for creating functional
    Superset charts. These rules cover common pitfalls, required fields per chart
    type, and tips for ensuring charts render correctly.

    Returns:
        String containing the expert rules for chart creation, formatted as
        readable text with guidelines organized by topic.
    """
    # Delegate to the rules module which contains the expert chart creation guide
    return rules.get_chart_creation_rules()


async def list_charts(manager: ConnectionManager, server_id: str) -> str:
    """
    MCP Tool: superset_list_charts - List all charts on a Superset server.

    Fetches the paginated list of all charts from the Superset API.
    Useful for discovering existing charts and their IDs before creating
    dashboards or making updates.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server to query.

    Returns:
        JSON string containing the paginated list of charts from GET /api/v1/chart/,
        including each chart's ID, name, viz_type, and datasource info.
    """
    # Delegate to the generic Superset API helper for the paginated GET request
    return await impl_superset_api(manager, server_id, "GET", "/api/v1/chart/")


async def get_chart_info(
    manager: ConnectionManager,
    server_id: str,
    chart_id: Union[int, str]
) -> str:
    """
    MCP Tool: superset_get_chart_info - Get detailed information about a specific chart.

    Fetches the complete configuration and metadata for a single chart, including
    its viz_type, params (as JSON), datasource reference, slice name, and description.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_id: The numeric (or string) ID of the chart to inspect.

    Returns:
        JSON string containing the full chart details from GET /api/v1/chart/{id},
        including slice_name, viz_type, params, datasource_id, datasource_type,
        and other metadata.
    """
    # Delegate to the generic Superset API helper for the GET request
    return await impl_superset_api(
       manager, server_id, "GET", f"/api/v1/chart/{chart_id}"
    )

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
    """
    # Step 1: Retrieve server context and validate it exists
    ctx = manager.get_context(server_id)
    if not ctx:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_generate_chart", status="error").inc()
        mc.record_error(tool="superset_generate_chart", error_message=f"Server '{server_id}' not found.")
        return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    # Step 2: Ensure chart types cache is available for validation
    known_types = await _ensure_chart_types_cached(manager, server_id)

    start_time = time.monotonic()
    try:
        # Step 3: Parse the config JSON string into a dict
        chart_config = json.loads(config) if config else {}

        viz_type = chart_config.get("viz_type", "table")
        actual_viz_type = _resolve_viz_type(viz_type)

        # Step 4: Validate viz_type against known chart types
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

        # Step 5: Auto-fix params (set defaults, remove invalid keys)
        fixed_params = auto_fix_chart_params(actual_viz_type, form_data)

        # Step 6: Fetch dataset schema (columns + metrics) for validation
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

        # Step 6b: Block if dataset schema fetch failed (exception, not just empty data)
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
        
        # Step 7: ── Column-level validation (with dataset columns available) ──
        if dataset_columns:
            fixed_params, column_warnings = resolve_chart_params(fixed_params, dataset_columns)
            if column_warnings:
                validation_warning = "Column fixes: " + "; ".join(column_warnings)
            else:
                validation_warning = None
            
            # Step 7a: Validate chart data against dataset BEFORE creating
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
            
            # Step 7b: Merge validation warnings
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
        
        # Step 8: ── Sankey validation (unconditional) ──
        sankey_warning = _validate_sankey_params(fixed_params, slice_name)
        if sankey_warning:
            return ChartError(
                sankey_warning["title"],
                details=sankey_warning["body"],
                status_code=400,
            ).to_json()
        
        # Step 9: ── Metric validation (blocks creation if errors found) ──
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
        
        # Step 10: ── Datasource compatibility (blocks creation if errors found) ──
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

        # Ensure datasource_id is in params
        if "datasource_id" not in fixed_params or fixed_params["datasource_id"] is None:
            fixed_params["datasource_id"] = dataset_id
        if "datasource" not in fixed_params:
            fixed_params["datasource"] = f"{dataset_id}__table"
        if "datasource_type" not in fixed_params:
            fixed_params["datasource_type"] = "table"

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


async def get_chart_preview(
    manager: ConnectionManager,
    server_id: str,
    chart_id: Union[int, str]
) -> str:
    """
    MCP Tool: superset_get_chart_preview - Get a visual preview URL for a chart.

    Generates URLs for previewing a chart in Superset's Explore interface or
    embedded in other pages. Useful for sharing chart links or embedding charts
    in external dashboards.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_id: The numeric (or string) ID of the chart to preview.

    Returns:
        JSON string containing:
          - preview_url: URL to view the chart in Superset's Explore interface
          - chart_id: The chart ID
          - embed_url: URL suitable for embedding in external pages
        Returns ChartError JSON if the server is not found.
    """
    # Step 1: Retrieve server context
    ctx = manager.get_context(server_id)
    if not ctx:
       return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
       # Step 2: Build the Explore URL for interactive preview
       base_url = ctx.config.base_url.rstrip("/")
       preview_url = f"{base_url}/explore/?slice_id={chart_id}"
       # Step 3: Build the embed URL for inline display
       embed_url = f"{base_url}/superset/slice/{chart_id}/"

       return ChartPreviewResponse(
           preview_url=preview_url,
           chart_id=int(chart_id),
           embed_url=embed_url,
       ).model_dump_json(indent=2)
    except Exception as e:
       return ChartError(f"Unexpected error getting chart preview: {e}", details=str(e)).to_json()


async def get_chart_data(
    manager: ConnectionManager,
    server_id: str,
    chart_id: Union[int, str]
) -> str:
    """
    MCP Tool: superset_get_chart_data - Fetch underlying data for a chart.

    Calls the chart's data endpoint to retrieve the raw data that the chart
    visualizes. Useful for debugging chart rendering issues, exporting data,
    or analyzing the query results that power a visualization.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_id: The numeric (or string) ID of the chart whose data to fetch.

    Returns:
        JSON string containing the chart's data from GET /api/v1/chart/{id}/data/,
        including the data rows, SQL query, row count, and execution metadata.
        Returns ChartError JSON if the request fails.
    """
    # Step 1: Retrieve server context
    ctx = manager.get_context(server_id)
    if not ctx:
       return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
       # Step 2: Execute the GET request to fetch the chart's underlying data
       endpoint = f"/api/v1/chart/{chart_id}/data/"
       resp = await execute_request(ctx, "GET", endpoint)
       resp.raise_for_status()
       return json.dumps(resp.json(), indent=2)
    except httpx.HTTPStatusError as e:
       return ChartError(
           f"HTTP {e.response.status_code} getting chart data",
           status_code=e.response.status_code,
           details=e.response.text,
       ).to_json()
    except Exception as e:
       return ChartError(f"Unexpected error getting chart data: {e}", details=str(e)).to_json()


async def get_chart_type_schema(
    manager: ConnectionManager,
    server_id: str,
    chart_type: str
) -> str:
    """
    MCP Tool: superset_get_chart_type_schema - Get schema for a specific chart type.

    Fetches the JSON schema for a specific chart type's parameters from the Superset API.
    The schema describes all valid parameters, their types, required fields, and default
    values. Useful for understanding what configuration options are available for a
    particular chart type.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_type: The Superset viz_type to get the schema for (e.g., 'echarts_bar',
            'echarts_timeseries_line', 'table').

    Returns:
        JSON string containing the chart type schema with the chart_type name and
        the raw schema object from the Superset API. Returns ChartError JSON if
        the schema cannot be retrieved.
    """
    # Step 1: Validate server context exists
    ctx = manager.get_context(server_id)
    if not ctx:
       return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        # Step 2: Fetch the schema from the Superset charts API
        result = await impl_superset_api(
            manager, server_id, "GET", f"/api/v1/chart/schemas/{chart_type}/"
        )
        # Step 3: Wrap the raw result in a ChartTypeSchema model for structured output
        return ChartTypeSchema(chart_type=chart_type, schema_data={"raw": result}).model_dump_json(indent=2)
    except Exception as e:
        return ChartError(f"Unexpected error getting chart type schema: {e}", details=str(e)).to_json()


async def get_all_chart_schemas(manager: ConnectionManager, server_id: str) -> str:
    """
    Dynamically discovers ALL chart types from Superset API,
    fetches each schema, and returns a consolidated Markdown reference.
    Cached for 24 hours to avoid repeated API calls.
    """
    import asyncio

    async def _fetch_schema(chart_type: str) -> Optional[Dict[str, Any]]:
        """Fetch the JSON schema for a single chart type from Superset API.

        Args:
            chart_type: The Superset viz_type string (e.g. "echarts_timeseries_line").

        Returns:
            Dict with ``"type"`` and ``"schema"`` keys on success,
            or None if the API call fails.
        """
        try:
            result = await impl_superset_api(
                manager, server_id, "GET", f"/api/v1/chart/schemas/{chart_type}/"
            )
            return {"type": chart_type, "schema": json.loads(result)}
        except Exception:
            return None

    def _parse_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a raw chart schema into categorized field lists.

        Extracts properties from the schema and classifies each field as
        metric, groupby/dimension, or other, plus a deduplicated required list.

        Args:
            schema: The raw JSON schema dict from the Superset API.

        Returns:
            Dict with keys: ``required``, ``metric_fields``, ``groupby_fields``,
            ``other_fields``. Each value is a list of formatted field strings.
        """
        properties = schema.get("properties", {})
        parsed_required = []

        # Check top-level "required" array
        if "required" in schema and isinstance(schema["required"], list):
            parsed_required = list(schema["required"])

        metric_fields = []
        groupby_fields = []
        other_fields = []

        for field_name, field_info in properties.items():
            if not isinstance(field_info, dict):
                other_fields.append(f"**{field_name}** (unknown)")
                continue
            field_type = str(field_info.get("type", "unknown"))
            description = field_info.get("description", "") or field_info.get("title", "")
            name_lower = field_name.lower()

            if any(kw in name_lower for kw in ["metric", "aggregate"]):
                metric_fields.append(f"**{field_name}** ({field_type}) - {description}")
            elif any(kw in name_lower for kw in ["group", "series", "dimension", "category", "x_axis", "y_", "slice"]):
                groupby_fields.append(f"**{field_name}** ({field_type}) - {description}")
            elif name_lower not in ("datasource", "viz_type", "slice_name", "description", "id"):
                other_fields.append(f"**{field_name}** ({field_type}) - {description}")

        # Check form_data if present
        form_data = schema.get("form_data", {})
        if isinstance(form_data, dict):
            fd_props = form_data.get("properties", {})
            fd_required = form_data.get("required", [])
            if isinstance(fd_required, list):
                parsed_required.extend(fd_required)
            for field_name, field_info in fd_props.items():
                if not isinstance(field_info, dict):
                    continue
                field_type = str(field_info.get("type", "unknown"))
                description = field_info.get("description", "") or field_info.get("title", "")
                name_lower = field_name.lower()
                if any(kw in name_lower for kw in ["metric", "aggregate"]):
                    metric_fields.append(f"**{field_name}** ({field_type}) - {description}")
                elif any(kw in name_lower for kw in ["group", "series", "dimension", "x_", "y_"]):
                    groupby_fields.append(f"**{field_name}** ({field_type}) - {description}")
                elif name_lower not in ("datasource", "viz_type", "slice_name", "description"):
                    other_fields.append(f"**{field_name}** ({field_type}) - {description}")

        return {
            "required": list(set(parsed_required)),
            "metric_fields": metric_fields,
            "groupby_fields": groupby_fields,
            "other_fields": other_fields,
        }

    def _build_markdown(all_schemas: List[Dict[str, Any]], cache_key: str) -> str:
        """Build a consolidated Markdown reference from parsed chart schemas.

        Generates a quick-reference table followed by detailed per-chart-type
        sections listing required, metric, groupby, and other fields.

        Args:
            all_schemas: List of dicts, each with ``type``, ``parsed``, and
                ``raw_schema`` keys from the discovery and parse phases.
            cache_key: Source identifier for the generated reference header.

        Returns:
            Complete Markdown string with the consolidated chart type reference.
        """
        lines = [
            "# Superset Chart Types - Complete Reference",
            "",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
            f"Source: Superset API ({cache_key})",
            "",
            "---",
            "",
            f"**Total chart types available: {len(all_schemas)}**",
            "",
            "## Quick Reference",
            "",
            "| # | Chart Type | Required Fields | Metric Fields | GroupBy Fields |",
            "|---|-----------|----------------|---------------|----------------|",
        ]

        for idx, item in enumerate(all_schemas, 1):
            chart_type = item["type"]
            parsed = item["parsed"]
            required_str = ", ".join(parsed["required"][:5]) if parsed["required"] else "See details"
            metric_count = len(parsed["metric_fields"])
            groupby_count = len(parsed["groupby_fields"])
            lines.append(f"| {idx} | `{chart_type}` | {required_str} | {metric_count} | {groupby_count} |")

        lines.extend(["", "---", "", "## Detailed Schemas", "", ""])

        for item in all_schemas:
            chart_type = item["type"]
            parsed = item["parsed"]
            raw = item.get("raw_schema", {})

            lines.append(f"### `{chart_type}`")
            lines.append("")

            if parsed["required"]:
                lines.append("**Required fields:**")
                for field in parsed["required"]:
                    lines.append(f"- `{field}`")
                lines.append("")

            if parsed["metric_fields"]:
                lines.append("**Metric fields:**")
                for f in parsed["metric_fields"][:10]:
                    lines.append(f"- {f}")
                if len(parsed["metric_fields"]) > 10:
                    lines.append(f"- ... and {len(parsed['metric_fields']) - 10} more")
                lines.append("")

            if parsed["groupby_fields"]:
                lines.append("**GroupBy/Dimension fields:**")
                for f in parsed["groupby_fields"][:10]:
                    lines.append(f"- {f}")
                if len(parsed["groupby_fields"]) > 10:
                    lines.append(f"- ... and {len(parsed['groupby_fields']) - 10} more")
                lines.append("")

            if parsed["other_fields"]:
                lines.append("**Other fields:**")
                for f in parsed["other_fields"][:10]:
                    lines.append(f"- {f}")
                if len(parsed["other_fields"]) > 10:
                    lines.append(f"- ... and {len(parsed['other_fields']) - 10} more")
                lines.append("")

            form_data = raw.get("form_data", {})
            if isinstance(form_data, dict) and form_data:
                lines.append("**Form data properties (top 15):**")
                fd_props = form_data.get("properties", {})
                for field_name, field_info in list(fd_props.items())[:15]:
                    if isinstance(field_info, dict):
                        field_type = str(field_info.get("type", "unknown"))
                        desc = field_info.get("description", "") or field_info.get("title", "")
                        lines.append(f"- `{field_name}`: {field_type} - {desc}")
                if len(fd_props) > 15:
                    lines.append(f"- ... and {len(fd_props) - 15} more")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    # --- Main logic ---
    # Step 1: Validate server context exists
    ctx = manager.get_context(server_id)
    if not ctx:
        return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    # Step 2: Check cache for previously fetched schemas (24-hour TTL)
    if os.path.isfile(CACHE_FILE):
        try:
            file_age = time.time() - os.path.getmtime(CACHE_FILE)
            if file_age < CACHE_TTL_SECONDS:
                with open(CACHE_FILE, "r") as f:
                    cached = json.load(f)
                return cached.get("markdown", json.dumps(cached, indent=2))
        except (json.JSONDecodeError, OSError):
            pass

    # Step 3: Fetch chart API info to discover all chart types
    try:
        info_raw = await impl_superset_api(manager, server_id, "GET", "/api/v1/chart/_info")
        info_data = json.loads(info_raw)
    except Exception as e:
        return ChartError(f"Failed to fetch chart API info: {e}", details=str(e)).to_json()

    # Step 4: Extract chart type names from _info response
    chart_types = []
    properties = info_data.get("result", {}).get("properties", {})

    if isinstance(properties, dict):
        # Check form_data.properties.viz_type.enum
        fd = properties.get("form_data", {})
        if isinstance(fd, dict):
            fd_props = fd.get("properties", {})
            viz_type = fd_props.get("viz_type", {})
            if isinstance(viz_type, dict):
                enum_vals = viz_type.get("enum", [])
                if enum_vals:
                    chart_types = [str(v) for v in enum_vals]

        # Check form_data.viz_type if form_data is a top-level property
        if not chart_types:
            form_data_prop = properties.get("form_data", {})
            if isinstance(form_data_prop, dict):
                fd_viz = form_data_prop.get("viz_type", {})
                if isinstance(fd_viz, dict):
                    enum_vals = fd_viz.get("enum", [])
                    if enum_vals:
                        chart_types = [str(v) for v in enum_vals]

        # Try properties.chart_types
        if not chart_types:
            ct = properties.get("chart_types", [])
            if isinstance(ct, list) and ct:
                chart_types = [str(c) for c in ct]

        # Try any property with an enum array
        if not chart_types:
            for key, val in properties.items():
                if isinstance(val, dict) and "enum" in val:
                    enum_vals = val.get("enum", [])
                    if isinstance(enum_vals, list) and len(enum_vals) > 2:
                        chart_types = [str(v) for v in enum_vals]
                        break

    if not chart_types:
        chart_types = list(TYPE_MAP.values())
        chart_types = list(set(chart_types))
        chart_types.sort()

    # Step 5: Fetch schemas for all chart types in parallel
    tasks = [_fetch_schema(ct) for ct in chart_types]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Step 6: Process results, building parsed schema entries for each chart type
    all_schemas = []
    for result in results:
        if isinstance(result, Exception):
            continue
        if result is None:
            continue
        try:
            parsed = _parse_schema(result["schema"])
            all_schemas.append({
                "type": result["type"],
                "parsed": parsed,
                "raw_schema": result["schema"],
            })
        except Exception:
            all_schemas.append({
                "type": result["type"],
                "parsed": {"required": [], "metric_fields": [], "groupby_fields": [], "other_fields": ["Schema parsing failed"]},
                "raw_schema": {},
            })

    all_schemas.sort(key=lambda x: x["type"])

    cache_key = f"Superset {info_data.get('result', {}).get('version', 'unknown')}"
    markdown = _build_markdown(all_schemas, cache_key)

    # Write cache
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump({
                "cache_key": cache_key,
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                "total_types": len(all_schemas),
                "chart_types": [s["type"] for s in all_schemas],
                "markdown": markdown,
            }, f, indent=2)
    except OSError:
        pass

    return markdown
