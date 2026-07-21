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
                return cached.get("chart_types", [])
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
    Retrieves metadata about the chart API.
    """
    return await impl_superset_api(manager, server_id, "GET", "/api/v1/chart/_info")

def _resolve_viz_type(viz_type: str) -> str:
    """Resolve a generic viz_type to the actual Superset viz_type using TYPE_MAP."""
    return TYPE_MAP.get(viz_type, viz_type)

def _extract_columns_from_dataset_response(response_str: str) -> List[Dict[str, Any]]:
    """Extract columns list from dataset API response."""
    try:
        data = json.loads(response_str)
        result = data.get("result", {})
        if isinstance(result, dict):
            columns = result.get("columns", [])
            if isinstance(columns, list):
                return columns
        return []
    except (json.JSONDecodeError, TypeError):
        return []

def _validate_metric_string_format(params: Dict[str, Any]) -> List[str]:
    """
    Basic syntax validation for metric strings.
    
    Runs when no dataset schema is available. Catches obviously wrong
    metric strings by parsing their format.
    """
    import re
    errors: List[str] = []
    
    def check_metric_string(ms: str, label: str) -> None:
        s = ms.strip()
        if not s:
            errors.append(f"Empty metric string in {label}")
            return
        s_lower = s.lower()
        if s_lower == "count":
            return  # built-in count is always valid
        # Must match AGG(col) format
        match = re.match(r"^(SUM|AVG|MIN|MAX|COUNT|COUNT_DISTINCT)\s*\(\s*.+?\s*\)$", s, re.IGNORECASE)
        if not match:
            errors.append(
                f"'{s}' in {label} has invalid format. "
                f"Expected 'count' or 'AGGREGATION(column_name)' "
                f"(e.g., 'SUM(sales)', 'AVG(price)')."
            )
    
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
    
    if "metrics" in params and params["metrics"]:
        for i, m in enumerate(params["metrics"]):
            if isinstance(m, str):
                check_metric_string(m, f"'metrics[{i}]'")
            elif isinstance(m, dict):
                col_name = m.get("column", {}).get("column_name")
                if not col_name:
                    errors.append(f"'metrics[{i}]' object has null or missing column_name")
    
    # Check 'entity' — null/empty entity for map types
    if "entity" in params and not params["entity"]:
        errors.append("'entity' is null or empty — set it to a valid column name (e.g., 'country_code')")

    # Check 'orderby' — format: [["col", true], ...] or [{"column": {"column_name": "x"}, "asc": true}, ...]
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
    
    # Check 'timeseries_limit_metric' — can be string, dict, or None
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
    
    Returns list of missing/invalid metric descriptions.
    """
    import re
    missing_metrics: List[str] = []
    dataset_metric_names = {m["metric_name"] for m in dataset_metrics}
    
    # Build column lookup for type checking
    column_map: Dict[str, Dict[str, Any]] = {}
    if dataset_columns:
        for col in dataset_columns:
            col_name = col.get("column_name", "")
            if col_name:
                column_map[col_name.lower()] = col
    
    def extract_metric_strings(p: Dict[str, Any]) -> List[str]:
        """Extract all metric strings from params."""
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
        """Parse 'SUM(sales)' into (aggregate, column_name). Both lowercase."""
        s = metric_str.strip().lower()
        if s == "count":
            return ("count", "count")
        m = re.match(r"^(sum|avg|min|max|count|count_distinct)\s*\(\s*(.+?)\s*\)$", s)
        if m:
            return (m.group(1), m.group(2).strip())
        return ("", s)
    
    def normalize_metric(metric_str: str) -> str:
        """Normalize metric string for comparison."""
        metric_str = metric_str.strip()
        if metric_str.lower() == "count":
            return "count"
        return metric_str.lower()
    
    def metric_matches(metric_name: str, target: str) -> bool:
        """Check if a dataset metric matches the target metric."""
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
        """Check if column type is compatible with aggregate. Returns error string or None."""
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
        
        # Special: reject COUNT(count) with parentheses — user likely meant bare "count"
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
        
        # Parse for column fallback
        parse_result = parse_metric_string(pm)
        agg, col_in_metric = parse_result
        
        # Built-in count — always valid if dataset exists
        if normalized == "count":
            if dataset_metric_names and not any(m.lower().startswith("count") for m in dataset_metric_names):
                missing_metrics.append(
                    f"'{pm}': 'count' is a built-in metric but no count-like metric was "
                    f"found in the dataset's defined metrics."
                )
            continue
        
        # Check if metric exists in predefined dataset metrics
        if dataset_metric_names:
            found = False
            for dm in dataset_metric_names:
                if metric_matches(dm, pm):
                    found = True
                    break
            if found:
                continue  # matched a predefined metric
        
        # Metric not in predefined list — try column fallback
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
        
        # No dataset_metrics and no dataset_columns — can't validate, BLOCK
        if not dataset_metric_names and not column_map:
            available = [c.get("column_name", "") for c in dataset_columns] if dataset_columns else []
            missing_metrics.append(
                f"'{pm}' cannot be validated because no dataset schema was retrieved. "
                f"Dataset returned no columns and no predefined metrics. "
                f"Verify the datasource exists and has columns defined."
            )
            continue
        
        # If we got here and have metrics, mark as missing
        if dataset_metric_names:
            missing_metrics.append(
                f"'{pm}' does not match any predefined metric in the dataset."
            )
    
    return missing_metrics

def _extract_chart_ids_from_position_json(position_json: str) -> List[int]:
    """Extract all chart IDs from a position JSON string."""
    chart_ids = []
    try:
        if isinstance(position_json, str):
            pos = json.loads(position_json)
        else:
            pos = position_json
        
        def walk(obj):
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
    """
    if "sankey_v2" not in params.get("viz_type", ""):
        return None
    
    errors = []
    
    # Validate required fields using the validation module
    from modules.SupersetModule.superset_validation import validate_chart_params
    validation_errors = validate_chart_params("sankey_v2", params)
    if validation_errors:
        errors.extend(validation_errors)
    
    if errors:
        return {"title": f"Chart '{slice_name}' - Sankey validation errors", 
                "body": "\n".join(errors) + "\n\nSankey charts require 'source' and 'target' fields."}
    
    # Check if cycle fix has already been suggested
    if params.get("_cycle_fix_suggested"):
        return None
    
    # Provide helpful cycle fix suggestion
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
    Blunt test: query the chart data endpoint and fail on ANY sign of trouble.
    
    Calls GET /api/v1/chart/{id}/data/. Blocks if:
      - HTTP status != 200
      - result has explicit 'error' field
      - result.status != 'success'
      - sql_rowcount is 0 or None (no data returned)
      - response contains error keywords in body text
    
    Only returns is_valid=True if data was returned with no errors.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return {"is_valid": False, "error": "Server context not found", "row_count": None}
    
    try:
        resp = await execute_request(ctx, "GET", f"/api/v1/chart/{chart_id}/data/")
        
        if resp.status_code != 200:
            return {"is_valid": False, "error": f"HTTP {resp.status_code}: {resp.text[:300]}", "row_count": None}
        
        data = resp.json()
        result = data.get("result", {})
        error = result.get("error")
        status = result.get("status", "unknown")
        row_count = result.get("sql_rowcount")
        
        # Explicit error field
        if error:
            return {"is_valid": False, "error": f"Data endpoint error: {error}", "row_count": row_count}
        
        # Non-success status
        if status != "success":
            return {"is_valid": False, "error": f"Data endpoint status: {status}", "row_count": row_count}
        
        # No rows returned → broken chart
        if not row_count or row_count == 0:
            return {"is_valid": False, "error": "Chart returned no data rows (sql_rowcount=0)", "row_count": 0}
        
        # Scan the FULL response text for error keywords
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
            return {"is_valid": False, "error": f"Chart response contains error keywords: {matches}", "row_count": row_count}
        
        # Success with data
        return {"is_valid": True, "error": None, "row_count": row_count}
    
    except httpx.HTTPStatusError as e:
        return {"is_valid": False, "error": f"HTTP {e.response.status_code}: {e.response.text[:300]}", "row_count": None}
    except Exception as e:
        return {"is_valid": False, "error": f"Data endpoint exception: {str(e)[:300]}", "row_count": None}

async def _delete_chart(
    manager: ConnectionManager,
    server_id: str,
    chart_id: int
) -> bool:
    """Delete a chart by ID. Returns True on success."""
    ctx = manager.get_context(server_id)
    if not ctx:
        return False
    
    try:
        resp = await execute_request(ctx, "DELETE", f"/api/v1/chart/{chart_id}")
        return resp.status_code in [200, 204]
    except Exception:
        return False

async def _validate_chart_on_datasource(
    manager: ConnectionManager,
    server_id: str,
    chart_id: int
) -> Dict[str, Any]:
    """
    Validate a chart against its datasource by testing the data endpoint.
    
    Returns validation result dict for use in dashboard creation.
    """
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
        
        # Get dataset columns
        try:
            ds_resp = await execute_request(ctx, "GET", f"/api/v1/dataset/{dataset_id}")
            ds = ds_resp.json().get("result", {})
            columns = ds.get("columns", [])
        except Exception:
            columns = []
        
        # Run compatibility validation
        from modules.SupersetModule.superset_validation import (
            validate_datasource_compatibility,
        )
        compat_errors = validate_datasource_compatibility(viz_type, params, columns)
        
        if compat_errors:
            return {
                "chart_id": chart_id,
                "is_valid": False,
                "error": "Compatibility: " + "; ".join(compat_errors),
                "viz_type": viz_type,
            }
        
        # Test the data endpoint
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
    manager: ConnectionManager,
    server_id: str,
    chart_id: int
) -> List[str]:
    """
    After creation, fetch the chart from Superset and verify its saved params
    have no null/empty values for critical fields.
    
    This catches cases where Superset's API accepted bad params (e.g., null metric)
    and stored them as-is, which later cause render-time errors.
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
        
        # Check metric (singular)
        if "metric" in params:
            m = params["metric"]
            if m is None:
                errors.append("saved 'metric' is null")
            elif isinstance(m, dict):
                col_name = m.get("column", {}).get("column_name")
                if col_name is None:
                    errors.append("saved 'metric' has null column_name")
        
        # Check metrics (array)
        if "metrics" in params and isinstance(params["metrics"], list):
            for i, m in enumerate(params["metrics"]):
                if m is None:
                    errors.append(f"saved 'metrics[{i}]' is null")
                elif isinstance(m, dict):
                    col_name = m.get("column", {}).get("column_name")
                    if col_name is None:
                        errors.append(f"saved 'metrics[{i}]' has null column_name")
        
        # Check orderby
        if "orderby" in params and isinstance(params["orderby"], list):
            for i, entry in enumerate(params["orderby"]):
                if isinstance(entry, list) and len(entry) >= 1 and entry[0] is None:
                    errors.append(f"saved 'orderby[{i}]' has null column reference")
                elif isinstance(entry, dict):
                    col_entry = entry.get("column", {})
                    if isinstance(col_entry, dict) and col_entry.get("column_name") is None:
                        errors.append(f"saved 'orderby[{i}]' has null column_name")
        
        # Check timeseries_limit_metric
        if "timeseries_limit_metric" in params and params["timeseries_limit_metric"] is None:
            errors.append("saved 'timeseries_limit_metric' is null")
        
        # Check entity
        if "entity" in params and not params["entity"]:
            errors.append("saved 'entity' is null or empty")
        
        # Check columns (sunburst, treemap, boxplot, etc.)
        if "columns" in params and isinstance(params["columns"], list):
            for i, col in enumerate(params["columns"]):
                if col is None:
                    errors.append(f"saved 'columns[{i}]' is null")
                elif isinstance(col, str) and not col.strip():
                    errors.append(f"saved 'columns[{i}]' is empty")
        
        # Check all_columns (table chart)
        if "all_columns" in params and isinstance(params["all_columns"], list):
            for i, col in enumerate(params["all_columns"]):
                if col is None:
                    errors.append(f"saved 'all_columns[{i}]' is null")
                elif isinstance(col, str) and not col.strip():
                    errors.append(f"saved 'all_columns[{i}]' is empty")
        
        # Check groupby
        if "groupby" in params and isinstance(params["groupby"], list):
            for i, col in enumerate(params["groupby"]):
                if col is None:
                    errors.append(f"saved 'groupby[{i}]' is null")
                elif isinstance(col, str) and not col.strip():
                    errors.append(f"saved 'groupby[{i}]' is empty")
        
        # Check granularity_sqla for time-based charts
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
    ctx = manager.get_context(server_id)
    if not ctx:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_create_chart", status="error").inc()
        mc.record_error(tool="superset_create_chart", error_message=f"Server '{server_id}' not found.")
        return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    # Ensure chart types cache is available
    known_types = await _ensure_chart_types_cached(manager, server_id)

    start_time = time.monotonic()
    try:
        actual_viz_type = _resolve_viz_type(viz_type)

        # Validate viz_type against known chart types
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
        try:
            dataset_response = await impl_superset_api(manager, server_id, "GET", f"/api/v1/dataset/{datasource_id}")
            dataset_data = json.loads(dataset_response)
            dataset_columns = dataset_data.get("result", {}).get("columns", [])
            dataset_metrics = dataset_data.get("result", {}).get("metrics", [])
        except Exception:
            pass
        
        # ── Metric validation (always runs, even when columns/metrics are empty) ──
        # When dataset_columns is empty, we can't check column existence, but we
        # still validate metric string format and run the post-creation data test.
        metric_errors = _validate_metrics_against_dataset(
            fixed_params, dataset_metrics, actual_viz_type, dataset_columns
        )
        
        # Even without schema data, validate metric string format (syntax check)
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

        # ── Column-level validation (only when dataset columns are available) ──
        if dataset_columns:
            fixed_params, column_warnings = resolve_chart_params(fixed_params, dataset_columns)
            if column_warnings:
                warning = "Column name fixes: " + "; ".join(column_warnings)
            else:
                warning = None
            
            # Validate Sankey charts for proper params
            sankey_warning = _validate_sankey_params(fixed_params, slice_name)
            if sankey_warning:
                if "error" in str(sankey_warning).lower() or "missing" in str(sankey_warning).lower():
                    return ChartError(
                        sankey_warning["title"],
                        details=sankey_warning["body"],
                        status_code=400,
                    ).to_json()
                else:
                    warning = f"Sankey: {sankey_warning['body']}"
            
            # Validate chart data against dataset BEFORE creating
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
            
            # Merge validation warnings
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
        
        # Validate datasource compatibility for known viz types
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

        # Ensure datasource_id is in params (required by Superset frontend)
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

        endpoint = "/api/v1/chart/"
        resp = await execute_request(ctx, "POST", endpoint, json=chart_payload)
        resp.raise_for_status()
        result = resp.json()

        # Post-creation: verify saved params have no null/empty values
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
        
        # Post-creation: test chart data endpoint to verify it renders
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
    return await impl_superset_api(manager, server_id, "PUT", f"/api/v1/chart/{chart_id}", json_body=json_body)

def get_standard_chart_params(viz_type: str, datasource_id: int, overrides_json: Optional[str] = None) -> str:
    """
    Returns a JSON string of standard parameters for a given visualization type.
    """
    overrides = json.loads(overrides_json) if overrides_json else {}
    params = rules.get_standard_chart_params(viz_type, datasource_id, **overrides)
    return json.dumps(params, indent=2)

def get_chart_creation_rules() -> str:
    """Returns the expert rules for creating functional Superset charts."""
    return rules.get_chart_creation_rules()


async def list_charts(manager: ConnectionManager, server_id: str) -> str:
    return await impl_superset_api(manager, server_id, "GET", "/api/v1/chart/")


async def get_chart_info(
    manager: ConnectionManager,
    server_id: str,
    chart_id: Union[int, str]
) -> str:
    return await impl_superset_api(
       manager, server_id, "GET", f"/api/v1/chart/{chart_id}"
    )

async def generate_chart(
    manager: ConnectionManager,
    server_id: str,
    dataset_id: int,
    config: str,
    slice_name: Optional[str] = None,
    save_chart: bool = True,
    description: Optional[str] = None
 ) -> str:
    ctx = manager.get_context(server_id)
    if not ctx:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_generate_chart", status="error").inc()
        mc.record_error(tool="superset_generate_chart", error_message=f"Server '{server_id}' not found.")
        return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    # Ensure chart types cache is available
    known_types = await _ensure_chart_types_cached(manager, server_id)

    start_time = time.monotonic()
    try:
        chart_config = json.loads(config) if config else {}

        viz_type = chart_config.get("viz_type", "table")
        actual_viz_type = _resolve_viz_type(viz_type)

        # Validate viz_type against known chart types
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
        try:
            dataset_response = await impl_superset_api(manager, server_id, "GET", f"/api/v1/dataset/{dataset_id}")
            dataset_columns = _extract_columns_from_dataset_response(dataset_response)
        except Exception:
            pass
        
        if dataset_columns:
            fixed_params, column_warnings = resolve_chart_params(fixed_params, dataset_columns)
            if column_warnings:
                validation_warning = "Column fixes: " + "; ".join(column_warnings)
            else:
                validation_warning = None
            
            # NEW: Validate chart data against dataset BEFORE creating
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
            
            # Merge validation warnings
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
        
        errors = validate_chart_params(actual_viz_type, fixed_params)
        validation_errors = format_error_summary(errors) if errors else None
        
        if validation_errors and not validation_warning:
            validation_warning = "Validation: " + validation_errors
        elif validation_errors and validation_warning:
            validation_warning = validation_warning + " | " + validation_errors

        if not save_chart:
            base_url = ctx.config.base_url.rstrip("/")
            explore_url = f"{base_url}/explore/?form_data={json.dumps(fixed_params)}"
            mc = get_metrics()
            mc.tool_calls.labels(tool="superset_generate_chart", status="success").inc()
            mc.tool_duration.labels(tool="superset_generate_chart").observe(time.monotonic() - start_time)
            result = {
                "url": explore_url,
                "saved": False,
                "config": fixed_params,
            }
            if validation_warning:
                result["_validation_warning"] = validation_warning
            return json.dumps(result, indent=2)

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
        resp = await execute_request(ctx, "POST", endpoint, json=chart_payload)
        resp.raise_for_status()
        result = resp.json()

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
            "chart_id": result.get("id"),
            "slice_name": chart_name,
            "url": f"{ctx.config.base_url.rstrip('/')}/chart/{result.get('id')}/",
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
    ctx = manager.get_context(server_id)
    if not ctx:
       return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
       base_url = ctx.config.base_url.rstrip("/")
       preview_url = f"{base_url}/explore/?slice_id={chart_id}"
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
    ctx = manager.get_context(server_id)
    if not ctx:
       return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
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
    ctx = manager.get_context(server_id)
    if not ctx:
       return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        result = await impl_superset_api(
            manager, server_id, "GET", f"/api/v1/chart/schemas/{chart_type}/"
        )
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
        try:
            result = await impl_superset_api(
                manager, server_id, "GET", f"/api/v1/chart/schemas/{chart_type}/"
            )
            return {"type": chart_type, "schema": json.loads(result)}
        except Exception:
            return None

    def _parse_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
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
    ctx = manager.get_context(server_id)
    if not ctx:
        return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    # Check cache
    if os.path.isfile(CACHE_FILE):
        try:
            file_age = time.time() - os.path.getmtime(CACHE_FILE)
            if file_age < CACHE_TTL_SECONDS:
                with open(CACHE_FILE, "r") as f:
                    cached = json.load(f)
                return cached.get("markdown", json.dumps(cached, indent=2))
        except (json.JSONDecodeError, OSError):
            pass

    # Fetch chart API info to discover all chart types
    try:
        info_raw = await impl_superset_api(manager, server_id, "GET", "/api/v1/chart/_info")
        info_data = json.loads(info_raw)
    except Exception as e:
        return ChartError(f"Failed to fetch chart API info: {e}", details=str(e)).to_json()

    # Extract chart type names from _info response
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

    # Fetch schemas for all chart types (parallel)
    tasks = [_fetch_schema(ct) for ct in chart_types]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
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
