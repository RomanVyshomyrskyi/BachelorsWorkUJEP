"""
Superset chart parameter validation and auto-fixing.

Prevents 'e.column is undefined' and 'Data error' frontend errors by catching
and fixing malformed chart params before they are sent to the Superset API.

The core issue: Superset's frontend expects specific nested structures
for metrics and axis values. When these structures are malformed, the
frontend crashes with TypeError when trying to access e.column.columnName.

Categorization matches ACTUAL working chart formats from Superset's own examples.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple


# ── Viz type categories – matches ACTUAL working chart formats ────────────────

# Single string metric:  "metric": "count"  or  "metric": "SUM(sales)"
SINGULAR_STRING_METRIC_TYPES: set = {
    "big_number",
    "big_number_total",
    "funnel",
    "gauge_chart",
    "graph_chart",
    "heatmap_v2",
    "sankey_v2",
    "sunburst_v2",
    "treemap_v2",
    "tree_chart",
    "word_cloud",
    "world_map",
}

# Single AdHocMetricObject:  "metric": {"aggregate": "SUM", "column": {...}}
SINGULAR_ADHOC_METRIC_TYPES: set = {
    "pie",
    "waterfall",
}

# Array of strings:  "metrics": ["count", "SUM(col)"]
STRING_METRICS_ARRAY_TYPES: set = {
    "echarts_timeseries_line",
    "echarts_timeseries_bar",
    "echarts_area",
    "echarts_timeseries_scatter",
    "bubble_v2",
    "box_plot",
    "parallel",
}

# Array of AdHocMetricObjects:  "metrics": [{"aggregate": "SUM", ...}]
ADHOC_METRICS_ARRAY_TYPES: set = {
    "mixed_timeseries",
    "pivot_table_v2",
}

# Mixed: accepts BOTH strings and objects in the array
MIXED_METRICS_TYPES: set = {
    "radar",
}

# No metric/metrics field at all
NO_METRICS_TYPES: set = {
    "table",
    "histogram_v2",
    "gantt_chart",
}

# Requires an 'entity' field for geographic mapping
ENTITY_REQUIRED_TYPES: set = {
    "world_map",
}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _is_adhoc_metric_object(val: Any) -> bool:
    """Check if a value is a properly formatted AdHocMetricObject dict."""
    if not isinstance(val, dict):
        return False
    column = val.get("column")
    if not isinstance(column, dict):
        return False
    return "column_name" in column


def _is_string_metric(val: Any) -> bool:
    """Check if a value is a valid string metric like 'count', 'SUM(col)', etc."""
    if not isinstance(val, str):
        return False
    return val.strip() != ""


def _parse_string_metric(metric_str: str) -> Tuple[str, str]:
    """
    Parse a string metric like 'SUM(sales)' or 'AVG(price)' into (aggregate, column_name).

    Returns ('AVG', 'unknown') if the metric doesn't match a known pattern.
    """
    metric_str = metric_str.strip()
    if metric_str.lower() == "count":
        return ("COUNT", "count")

    match = re.match(
        r"^(SUM|AVG|MIN|MAX|COUNT|COUNT_DISTINCT)\s*\(\s*(.+?)\s*\)$",
        metric_str,
        re.IGNORECASE,
    )
    if match:
        return (match.group(1).upper(), match.group(2).strip())

    return ("AVG", metric_str)


def _build_adhoc_metric_from_string(metric_str: str) -> Dict[str, Any]:
    """Convert a string metric like 'SUM(sales)' to an AdHocMetricObject."""
    agg, col_name = _parse_string_metric(metric_str)
    return {
        "aggregate": agg,
        "column": {"column_name": col_name},
        "expressionType": "SIMPLE",
        "label": f"{agg}({col_name})",
    }


# ── Validation ───────────────────────────────────────────────────────────────


def validate_chart_params(viz_type: str, params: Dict[str, Any]) -> List[str]:
    """
    Validate chart params and return a list of human-readable error messages.

    Returns an empty list if params are valid.
    """
    errors: List[str] = []
    actual_viz = viz_type

    # --- Check 1: entity field for map types ---
    if actual_viz in ENTITY_REQUIRED_TYPES:
        if "entity" not in params:
            errors.append(
                f"Chart '{actual_viz}' is missing required 'entity' field. "
                f"Add: 'entity': 'country_code' (or the column with country identifiers)."
            )

    # --- Check 2: metric vs metrics (singular vs plural) based on viz type ---

    if actual_viz in SINGULAR_STRING_METRIC_TYPES:
        # Should have "metric": "string_value"
        if "metric" not in params and "metrics" not in params:
            errors.append(
                f"Chart '{actual_viz}' is missing 'metric' field. "
                f"Add: 'metric': 'count' (or 'SUM(column_name)')."
            )
        elif "metrics" in params and "metric" not in params:
            errors.append(
                f"Chart '{actual_viz}' uses 'metrics' (plural array) but should use "
                f"'metric' (singular string). Change 'metrics: [...]' to "
                f"'metric: \"count\"'."
            )
        elif "metric" in params:
            if not _is_string_metric(params["metric"]):
                if not _is_adhoc_metric_object(params["metric"]):
                    errors.append(
                        f"Chart '{actual_viz}' has invalid 'metric' format. "
                        f"Expected a string (e.g., 'count', 'SUM(column)') or an "
                        f"AdHocMetricObject."
                    )

    elif actual_viz in SINGULAR_ADHOC_METRIC_TYPES:
        # Should have "metric": {...AdHocMetricObject...}
        if "metrics" in params and "metric" not in params:
            errors.append(
                f"Chart '{actual_viz}' uses 'metrics' (plural array) but should use "
                f"'metric' (singular AdHocMetricObject). Change 'metrics: [...]' to "
                f"'metric: {{'aggregate': 'AVG', 'column': {{'column_name': '...'}}, "
                f"'expressionType': 'SIMPLE'}}'."
            )
        elif "metric" in params:
            metric_val = params["metric"]
            if _is_string_metric(metric_val):
                pass  # Accept strings – auto-fix will convert
            elif isinstance(metric_val, dict):
                if not _is_adhoc_metric_object(metric_val):
                    errors.append(
                        f"Metric object in '{actual_viz}' is missing "
                        f"'column.column_name'. Expected: {{'aggregate': 'AVG', "
                        f"'column': {{'column_name': '...'}}, "
                        f"'expressionType': 'SIMPLE'}}"
                    )

    elif actual_viz in STRING_METRICS_ARRAY_TYPES:
        # Should have "metrics": ["count", "SUM(col)"] or AdHocMetricObjects
        if "metrics" not in params:
            errors.append(
                f"Chart '{actual_viz}' is missing 'metrics' field. "
                f"Add: 'metrics': ['count']."
            )
        elif "metric" in params and "metrics" not in params:
            errors.append(
                f"Chart '{actual_viz}' uses 'metric' (singular) but should use "
                f"'metrics' (array)."
            )
        elif "metrics" in params:
            metrics_list = params["metrics"]
            if isinstance(metrics_list, list):
                for i, m in enumerate(metrics_list):
                    if isinstance(m, dict):
                        if not _is_adhoc_metric_object(m):
                            errors.append(
                                f"Metric {i} in '{actual_viz}' has invalid format. "
                                f"Expected AdHocMetricObject with 'column.column_name'."
                            )

    elif actual_viz in ADHOC_METRICS_ARRAY_TYPES:
        # Should have "metrics": [{"aggregate": "SUM", ...}]
        if "metrics" not in params:
            errors.append(
                f"Chart '{actual_viz}' is missing 'metrics' field. "
                f"Add: 'metrics': [{{'aggregate': 'SUM', 'column': {{'column_name': '...'}}, "
                f"'expressionType': 'SIMPLE'}}]."
            )
        elif "metric" in params and "metrics" not in params:
            errors.append(
                f"Chart '{actual_viz}' uses 'metric' (singular) but should use "
                f"'metrics' (array of AdHocMetricObjects)."
            )
        elif "metrics" in params:
            metrics_list = params["metrics"]
            if isinstance(metrics_list, list):
                for i, m in enumerate(metrics_list):
                    if _is_string_metric(m):
                        pass  # Accept strings as fallback
                    elif isinstance(m, dict):
                        if not _is_adhoc_metric_object(m):
                            errors.append(
                                f"Metric {i} in '{actual_viz}' is missing "
                                f"'column.column_name'. Expected: {{'aggregate': 'AVG', "
                                f"'column': {{'column_name': '...'}}, "
                                f"'expressionType': 'SIMPLE'}}"
                            )

    elif actual_viz in MIXED_METRICS_TYPES:
        # radar – accept both strings and objects
        if "metrics" not in params:
            errors.append(
                f"Chart '{actual_viz}' is missing 'metrics' field. "
                f"Add: 'metrics': ['count']."
            )
        elif "metric" in params and "metrics" not in params:
            errors.append(
                f"Chart '{actual_viz}' uses 'metric' (singular) but should use "
                f"'metrics' (array)."
            )
        elif "metrics" in params:
            metrics_list = params["metrics"]
            if isinstance(metrics_list, list):
                for i, m in enumerate(metrics_list):
                    if _is_string_metric(m):
                        pass  # OK
                    elif isinstance(m, dict):
                        if not _is_adhoc_metric_object(m):
                            errors.append(
                                f"Metric {i} in '{actual_viz}' is missing "
                                f"'column.column_name'."
                            )
                    else:
                        errors.append(
                            f"Metric {i} in '{actual_viz}' has invalid type. "
                            f"Expected string or AdHocMetricObject."
                        )

    elif actual_viz in NO_METRICS_TYPES:
        # table, histogram_v2, gantt_chart – no metrics field
        if "metric" in params or "metrics" in params:
            errors.append(
                f"Chart '{actual_viz}' should not have a 'metric' or 'metrics' field."
            )

    # --- Check 3: Nested column structure for scatter/bubble axes ---
    if actual_viz in {"scatter", "echarts_timeseries_scatter", "bubble_v2"}:
        for axis in ["x", "y"]:
            if axis in params:
                val = params[axis]
                if isinstance(val, dict):
                    if "column_name" in val and "column" not in val:
                        errors.append(
                            f"'{axis}' in '{actual_viz}' has 'column_name' at top level. "
                            f"Wrap it: '{axis}: {{'column': {{'column_name': '...'}}, "
                            f"'expressionType': 'DIMENSION'}}'."
                        )
                    elif "column" in val and isinstance(val["column"], str):
                        errors.append(
                            f"'{axis}' in '{actual_viz}' has 'column' as a string. "
                            f"Wrap it: '{axis}: {{'column': {{'column_name': '...'}}, "
                            f"'expressionType': 'DIMENSION'}}'."
                        )

    # --- Check 4: Required fields for AdHocMetricObjects ---
    if actual_viz in SINGULAR_ADHOC_METRIC_TYPES and "metric" in params:
        metric_val = params["metric"]
        if isinstance(metric_val, dict) and _is_adhoc_metric_object(metric_val):
            if "aggregate" not in metric_val:
                errors.append(
                    f"Metric in '{actual_viz}' missing 'aggregate' field. "
                    f"Add: 'aggregate': 'AVG' (or SUM, MIN, MAX, COUNT, COUNT_DISTINCT)."
                )
            if "expressionType" not in metric_val:
                errors.append(
                    f"Metric in '{actual_viz}' missing 'expressionType' field. "
                    f"Add: 'expressionType': 'SIMPLE'."
                )

    return errors


def auto_fix_chart_params(viz_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Auto-fix common parameter mistakes.

    Returns a new params dict with corrections applied. Always call
    validate_chart_params() after to check for remaining errors.
    """
    fixed = json.loads(json.dumps(params))  # deep copy
    actual_viz = viz_type

    # --- Fix 0: Ensure datasource_id is always present and is an integer ---
    if "datasource_id" in fixed and isinstance(fixed.get("datasource_id"), str):
        try:
            fixed["datasource_id"] = int(fixed["datasource_id"])
        except (ValueError, TypeError):
            pass

    # --- Fix 1: Entity field for map types ---
    if actual_viz in ENTITY_REQUIRED_TYPES:
        if "entity" not in fixed:
            fixed["entity"] = "country_code"

    # --- Fix 2: Pie/waterfall — groupby must be string, not array ---
    if actual_viz in SINGULAR_ADHOC_METRIC_TYPES and "groupby" in fixed:
        groupby = fixed["groupby"]
        if isinstance(groupby, list) and len(groupby) == 1:
            fixed["groupby"] = groupby[0]
        elif isinstance(groupby, list) and len(groupby) > 1:
            fixed["groupby"] = groupby[0]
        elif not isinstance(groupby, str):
            fixed["groupby"] = ""

    # --- Fix 3: Pie/waterfall — metrics array → metric object ---
    if actual_viz in SINGULAR_ADHOC_METRIC_TYPES and "metrics" in fixed and "metric" not in fixed:
        metric_list = fixed["metrics"]
        if isinstance(metric_list, list) and len(metric_list) > 0:
            first = metric_list[0]
            if _is_string_metric(first):
                fixed["metric"] = _build_adhoc_metric_from_string(first)
            elif isinstance(first, dict):
                fixed["metric"] = first
        if "metrics" in fixed:
            del fixed["metrics"]

    # --- Fix 4: Pie/waterfall — string metric → AdHocMetricObject ---
    if actual_viz in SINGULAR_ADHOC_METRIC_TYPES:
        if "metric" in fixed and _is_string_metric(fixed["metric"]):
            fixed["metric"] = _build_adhoc_metric_from_string(fixed["metric"])

    # --- Fix 5: Scatter/bubble — flat column_name → nested column object ---
    if actual_viz in {"scatter", "echarts_timeseries_scatter", "bubble_v2"}:
        for axis in ["x", "y"]:
            if axis in fixed and isinstance(fixed[axis], dict):
                val = fixed[axis]
                if "column_name" in val and "column" not in val:
                    column_name = val.pop("column_name")
                    expr_type = val.pop("expressionType", "DIMENSION")
                    fixed[axis] = {
                        "column": {"column_name": column_name},
                        "expressionType": expr_type,
                    }
                elif "column" in val and isinstance(val["column"], str):
                    column_name = val["column"]
                    expr_type = val.pop("expressionType", "DIMENSION")
                    del val["column"]
                    val["column"] = {"column_name": column_name}
                    val["expressionType"] = expr_type

    # --- Fix 6: String array types — fix malformed objects only, keep strings ---
    if actual_viz in STRING_METRICS_ARRAY_TYPES and "metrics" in fixed:
        metrics_list = fixed["metrics"]
        if isinstance(metrics_list, list):
            for i, m in enumerate(metrics_list):
                if isinstance(m, dict) and not _is_adhoc_metric_object(m):
                    if "column_name" in m and "column" not in m:
                        column_name = m.pop("column_name")
                        m["column"] = {"column_name": column_name}
                    if "aggregate" not in m:
                        m["aggregate"] = "AVG"
                    if "expressionType" not in m:
                        m["expressionType"] = "SIMPLE"

    # --- Fix 7: Ensure AdHocMetricObject has required fields ---
    if actual_viz in SINGULAR_ADHOC_METRIC_TYPES and "metric" in fixed:
        metric_val = fixed["metric"]
        if isinstance(metric_val, dict):
            if "column_name" in metric_val and "column" not in metric_val:
                column_name = metric_val.pop("column_name")
                metric_val["column"] = {"column_name": column_name}
            # Fix null column_name — replace with first available column
            if metric_val.get("column", {}).get("column_name") is None:
                if "groupby" in metric_val:
                    metric_val["column"]["column_name"] = metric_val.pop("groupby")
                else:
                    metric_val["column"]["column_name"] = "count"
            if "aggregate" not in metric_val:
                metric_val["aggregate"] = "AVG"
            if "expressionType" not in metric_val:
                metric_val["expressionType"] = "SIMPLE"

    # --- Fix 8: AdHoc metrics array types — fix malformed objects only ---
    if actual_viz in ADHOC_METRICS_ARRAY_TYPES and "metrics" in fixed:
        metrics_list = fixed["metrics"]
        if isinstance(metrics_list, list):
            for i, m in enumerate(metrics_list):
                if isinstance(m, dict) and not _is_adhoc_metric_object(m):
                    if "column_name" in m and "column" not in m:
                        column_name = m.pop("column_name")
                        m["column"] = {"column_name": column_name}
                    if "aggregate" not in m:
                        m["aggregate"] = "AVG"
                    if "expressionType" not in m:
                        m["expressionType"] = "SIMPLE"

    # --- Fix 9: Mixed metrics types — fix malformed objects only ---
    if actual_viz in MIXED_METRICS_TYPES and "metrics" in fixed:
        metrics_list = fixed["metrics"]
        if isinstance(metrics_list, list):
            for i, m in enumerate(metrics_list):
                if isinstance(m, dict) and not _is_adhoc_metric_object(m):
                    if "column_name" in m and "column" not in m:
                        column_name = m.pop("column_name")
                        m["column"] = {"column_name": column_name}
                    if "aggregate" not in m:
                        m["aggregate"] = "AVG"
                    if "expressionType" not in m:
                        m["expressionType"] = "SIMPLE"

    return fixed


def format_error_summary(errors: List[str]) -> str:
    """Format validation errors into a readable string."""
    if not errors:
        return "No errors found. Parameters are valid."
    lines = [f"Found {len(errors)} error(s):"]
    for i, err in enumerate(errors, 1):
        lines.append(f"  {i}. {err}")
    return "\n".join(lines)
