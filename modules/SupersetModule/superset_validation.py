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

# Requires source/target fields and validates DAG structure
SANKEY_TYPES: set = {
    "sankey_v2",
}

# Viz types that need specific datasource column types for compatibility
# Key = viz_type, Value = required column patterns
# Each pattern: {"required": [...], "optional": [...], "x_axis_temporal": bool}
DATASOURCE_REQUIREMENTS: Dict[str, Dict[str, Any]] = {
    "world_map": {
        "required": ["entity"],
        "optional": ["groupby"],
        "description": "world_map needs entity field (geographic identifier like country_code, zipcode)",
    },
    "bubble_v2": {
        "required": ["x", "y", "size"],
        "optional": ["series", "entity"],
        "description": "bubble_v2 needs x, y, and size field references",
    },
    "heatmap_v2": {
        "required": ["x_axis", "groupby"],
        "optional": [],
        "description": "heatmap_v2 needs x_axis and groupby (row dimension)",
    },
    "sunburst_v2": {
        "required": ["columns"],
        "optional": ["metric"],
        "description": "sunburst_v2 needs columns field (array of hierarchy levels)",
    },
    "treemap_v2": {
        "required": [],
        "optional": ["groupby"],
        "description": "treemap_v2 works with groupby or columns for hierarchy",
    },
    "radar": {
        "required": ["groupby"],
        "optional": ["metrics"],
        "description": "radar needs groupby for dimension labels",
    },
    "parallel": {
        "required": ["dimensions"],
        "optional": ["metrics"],
        "description": "parallel needs dimensions field (array of column names)",
    },
    "box_plot": {
        "required": ["groupby"],
        "optional": ["metric"],
        "description": "box_plot needs groupby for categories",
    },
    "histogram_v2": {
        "required": ["x_axis"],
        "optional": ["groupby", "metric"],
        "description": "histogram_v2 needs x_axis for the value to bin",
    },
    "waterfall": {
        "required": ["groupby"],
        "optional": ["metric"],
        "description": "waterfall needs groupby for categories",
    },
    "funnel": {
        "required": ["groupby"],
        "optional": ["metric"],
        "description": "funnel needs groupby for steps",
    },
    "gauge_chart": {
        "required": [],
        "optional": ["groupby", "metric"],
        "description": "gauge_chart is flexible, works with count or custom metric",
    },
    "echarts_timeseries_line": {
        "required": [],
        "optional": ["x_axis"],
        "x_axis_temporal": True,
        "description": "time series works best with temporal x_axis (date/time column)",
    },
    "echarts_area": {
        "required": [],
        "optional": ["x_axis"],
        "x_axis_temporal": True,
        "description": "area chart works best with temporal x_axis (date/time column)",
    },
    "big_number": {
        "required": [],
        "optional": ["x_axis"],
        "x_axis_temporal_for_trendline": True,
        "description": "big_number with trendline needs temporal x_axis",
    },
}


# ── Helpers ──────────────────────────────────────────────────────────────────


INVALID_METRIC_STRINGS: set = {
    "undefined", "null", "none", "",
}


def _is_adhoc_metric_object(val: Any) -> bool:
    """Check if a value is a properly formatted AdHocMetricObject dict."""
    if not isinstance(val, dict):
        return False
    column = val.get("column")
    if not isinstance(column, dict):
        return False
    column_name = column.get("column_name")
    return bool(column_name and isinstance(column_name, str))


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
        if not params.get("entity"):
            errors.append(
                f"Chart '{actual_viz}' is missing required 'entity' field. "
                f"Add: 'entity': 'country_code' (or the column with country identifiers)."
            )

    # --- Check 1.5: Sankey charts require source/target fields ---
    if actual_viz in SANKEY_TYPES:
        if "source" not in params:
            errors.append(
                f"Chart '{actual_viz}' is missing required 'source' field. "
                f"Add: 'source': 'channel_1' (the source column name)."
            )
        if "target" not in params:
            errors.append(
                f"Chart '{actual_viz}' is missing required 'target' field. "
                f"Add: 'target': 'channel_2' (the target column name)."
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
            metric_val = params["metric"]
            if metric_val is None:
                errors.append(
                    f"Chart '{actual_viz}' has null 'metric'. "
                    f"Set it to 'count' or 'SUM(column_name)'."
                )
            elif _is_string_metric(metric_val):
                ms = metric_val.strip().lower()
                if ms in INVALID_METRIC_STRINGS:
                    errors.append(
                        f"Chart '{actual_viz}' has invalid metric string "
                        f"'{metric_val}'. Use a real metric like 'count' "
                        f"or 'SUM(column_name)'."
                    )
            elif not _is_adhoc_metric_object(metric_val):
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
            if metric_val is None:
                errors.append(
                    f"Chart '{actual_viz}' has null 'metric'. "
                    f"Set it to a valid metric like 'count' or 'SUM(column_name)'."
                )
            elif _is_string_metric(metric_val):
                ms = metric_val.strip().lower()
                if ms in INVALID_METRIC_STRINGS:
                    errors.append(
                        f"Chart '{actual_viz}' has invalid metric string "
                        f"'{metric_val}'. Use a real metric like 'count' "
                        f"or 'SUM(column_name)'."
                    )
            elif isinstance(metric_val, dict) and not _is_adhoc_metric_object(metric_val):
                errors.append(
                    f"Metric object in '{actual_viz}' is missing or has null "
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
                    elif _is_string_metric(m):
                        ms = m.strip().lower()
                        if ms in INVALID_METRIC_STRINGS:
                            errors.append(
                                f"Metric {i} in '{actual_viz}' has invalid metric string "
                                f"'{m}'. Use a real metric like 'count' or 'SUM(column_name)'."
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
                        ms = m.strip().lower()
                        if ms in INVALID_METRIC_STRINGS:
                            errors.append(
                                f"Metric {i} in '{actual_viz}' has invalid metric string "
                                f"'{m}'. Use a real metric like 'count' or 'SUM(column_name)'."
                            )
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
                        ms = m.strip().lower()
                        if ms in INVALID_METRIC_STRINGS:
                            errors.append(
                                f"Metric {i} in '{actual_viz}' has invalid metric string "
                                f"'{m}'. Use a real metric like 'count' or 'SUM(column_name)'."
                            )
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

    # --- Check 5: Duplicate metric/column labels ---
    labels_seen: set = set()
    # Collect labels from 'metric' (singular)
    if "metric" in params:
        m = params["metric"]
        if isinstance(m, str):
            labels_seen.add(m.strip().lower())
        elif isinstance(m, dict):
            label = m.get("label", "") or f"{m.get('aggregate', '')}({m.get('column', {}).get('column_name', '')})"
            if label:
                labels_seen.add(label.lower())

    # Collect labels from 'metrics' (array)
    if "metrics" in params and isinstance(params["metrics"], list):
        for i, m in enumerate(params["metrics"]):
            label = None
            if isinstance(m, str):
                label = m.strip().lower()
            elif isinstance(m, dict):
                label = (m.get("label") or f"{m.get('aggregate', '')}({m.get('column', {}).get('column_name', '')})").lower()
            if label and label in labels_seen:
                errors.append(
                    f"Duplicate metric label '{label}' in metrics[{i}]. "
                    f"All metrics must have unique labels. "
                    f"Use different column names or set explicit 'label' fields."
                )
            elif label:
                labels_seen.add(label)

    # Collect labels from 'groupby' (can conflict with metric labels)
    if "groupby" in params:
        gb = params["groupby"]
        if isinstance(gb, list):
            for col in gb:
                if isinstance(col, str) and col.strip().lower() in labels_seen:
                    errors.append(
                        f"Duplicate label: groupby column '{col}' conflicts with "
                        f"a metric with the same label. Rename one of them."
                    )
        elif isinstance(gb, str) and gb.strip().lower() in labels_seen:
            errors.append(
                f"Duplicate label: groupby column '{gb}' conflicts with "
                f"a metric with the same label. Rename one of them."
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
        if not fixed.get("entity"):
            fixed["entity"] = "country_code"

    # --- Fix 1.5: Sankey charts — add cycle-breaking SQL hint ---
    if actual_viz in SANKEY_TYPES:
        if "source" in fixed and "target" in fixed:
            source_col = fixed["source"]
            target_col = fixed["target"]
            if "_cycle_fix_suggested" not in fixed:
                fixed["_cycle_fix_suggested"] = True
                fixed["_cycle_fix_sql"] = (
                    f"Add 'AND {source_col} < {target_col}' to the dataset SQL HAVING clause "
                    f"to break graph cycles. Example: "
                    f"HAVING {source_col} <> {target_col} AND {source_col} < {target_col}"
                )

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

    # --- Fix 3.1: SINGULAR_STRING_METRIC_TYPES — metrics array → metric string ---
    if actual_viz in SINGULAR_STRING_METRIC_TYPES and "metrics" in fixed and "metric" not in fixed:
        metric_list = fixed["metrics"]
        if isinstance(metric_list, list) and len(metric_list) > 0:
            first = metric_list[0]
            if isinstance(first, str):
                fixed["metric"] = first
            elif isinstance(first, dict):
                col = first.get("column", {}).get("column_name", "count")
                agg = first.get("aggregate", "AVG")
                fixed["metric"] = f"{agg}({col})"
        if "metrics" in fixed:
            del fixed["metrics"]

    # --- Fix 4: Singular metric types — string metric → AdHocMetricObject ---
    # SINGULAR_ADHOC_METRIC_TYPES (pie, waterfall) MUST have ad-hoc objects always.
    if actual_viz in SINGULAR_ADHOC_METRIC_TYPES:
        if "metric" in fixed and _is_string_metric(fixed["metric"]):
            fixed["metric"] = _build_adhoc_metric_from_string(fixed["metric"])
    # SINGULAR_STRING_METRIC_TYPES (big_number, funnel, etc.) accept strings,
    # but should still convert to ad-hoc for Superset 6.x — except bare 'count'.
    if actual_viz in SINGULAR_STRING_METRIC_TYPES:
        if "metric" in fixed and _is_string_metric(fixed["metric"]):
            if fixed["metric"].strip().lower() != "count":
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
                # Check if groupby is in the metric object itself
                if "groupby" in metric_val:
                    metric_val["column"]["column_name"] = metric_val.pop("groupby")
                # Check if groupby is at the top level of params (common for pie charts)
                elif "groupby" in fixed and fixed["groupby"]:
                    gb = fixed["groupby"]
                    if isinstance(gb, list) and len(gb) > 0:
                        metric_val["column"]["column_name"] = gb[0]
                    elif isinstance(gb, str):
                        metric_val["column"]["column_name"] = gb
                    else:
                        metric_val["column"]["column_name"] = "count"
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

    # --- Fix 10: big_number — ensure temporal column for dashboard rendering ---
    # big_number charts in dashboards need granularity_sqla to render properly
    if actual_viz == "big_number":
        if "granularity_sqla" not in fixed:
            # Add a default temporal column if dataset has one
            if "datasource_id" in fixed:
                fixed["_needs_temporal_check"] = True
            else:
                fixed["granularity_sqla"] = "ds"  # Common default

    # --- Fix 11: Pie chart — groupby must be array in dashboard context ---
    # When used in dashboards, pie charts require groupby as array, not string
    if actual_viz in SINGULAR_ADHOC_METRIC_TYPES and "groupby" in fixed:
        groupby = fixed["groupby"]
        # In dashboard context, groupby should be an array for proper rendering
        if isinstance(groupby, str) and groupby:
            fixed["groupby"] = [groupby]

    # --- Fix 12: big_number — ensure time config for dashboard rendering ---
    if actual_viz == "big_number":
        if "time_range" not in fixed:
            fixed["time_range"] = "100 years ago : now"
        if "adhoc_filters" not in fixed:
            fixed["adhoc_filters"] = []

    # --- Fix 13: General null column_name fix for ALL metric types ---
    # Prevents "Cannot compile Column object until its 'name' is assigned"
    # by replacing null column_name with first available groupby or 'count'
    if actual_viz not in NO_METRICS_TYPES:
        # Get fallback column name from groupby
        fallback_col = "count"
        groupby = fixed.get("groupby")
        if isinstance(groupby, list) and len(groupby) > 0:
            fallback_col = groupby[0]
        elif isinstance(groupby, str) and groupby.strip():
            fallback_col = groupby.strip()

        # Fix singular metric (big_number_total, funnel, world_map, etc.)
        if "metric" in fixed and fixed["metric"] is None:
            fixed["metric"] = fallback_col
        elif "metric" in fixed and isinstance(fixed["metric"], dict):
            metric_col = fixed["metric"].get("column", {})
            if isinstance(metric_col, dict) and not metric_col.get("column_name"):
                fixed["metric"]["column"]["column_name"] = fallback_col
                if "expressionType" not in fixed["metric"]:
                    fixed["metric"]["expressionType"] = "SIMPLE"

        # Fix array metrics (timeseries, bubble, etc.)
        if "metrics" in fixed and isinstance(fixed["metrics"], list):
            for m in fixed["metrics"]:
                if isinstance(m, dict):
                    metric_col = m.get("column", {})
                    if isinstance(metric_col, dict) and not metric_col.get("column_name"):
                        m["column"]["column_name"] = fallback_col
                        if "expressionType" not in m:
                            m["expressionType"] = "SIMPLE"

        # Fix 'timeseries_limit_metric' — replace null with fallback
        if "timeseries_limit_metric" in fixed:
            tlm = fixed["timeseries_limit_metric"]
            if tlm is None:
                fixed["timeseries_limit_metric"] = fallback_col
            elif isinstance(tlm, dict):
                col_name = tlm.get("column", {}).get("column_name")
                if col_name is None:
                    tlm.setdefault("column", {})["column_name"] = fallback_col

    # --- Fix 13b: Universal orderby cleanup (runs for ALL chart types) ---
    # Drops orderby entries with null/empty column references instead of
    # substituting fallback values, which would be invalid sort columns.
    if "orderby" in fixed and isinstance(fixed["orderby"], list):
        clean_orderby = []
        for entry in fixed["orderby"]:
            if isinstance(entry, list) and len(entry) >= 1:
                if entry[0] is None or (isinstance(entry[0], str) and not entry[0].strip()):
                    continue
                clean_orderby.append(entry)
            elif isinstance(entry, dict):
                col_entry = entry.get("column")
                if col_entry is None or not isinstance(col_entry, dict):
                    continue  # column is null, missing, or not a dict — drop
                col_name = col_entry.get("column_name")
                if col_name is None or (isinstance(col_name, str) and not col_name.strip()):
                    continue  # column_name is null/empty — drop
                clean_orderby.append(entry)
        fixed["orderby"] = clean_orderby

    # --- Fix 13c: columns / all_columns — drop null/empty entries ---
    # Sunburst, treemap, word_cloud, table use columns/all_columns arrays.
    # Null entries cause 'Field may not be null' validation errors.
    # Delete the key entirely if array ends up empty (also triggers null error).
    for field in ["columns", "all_columns"]:
        if field in fixed and isinstance(fixed[field], list):
            cleaned = [
                c for c in fixed[field]
                if c is not None and (not isinstance(c, str) or c.strip())
            ]
            if cleaned:
                fixed[field] = cleaned
            else:
                del fixed[field]

    # --- Fix 17: Time series + big_number — ensure granularity_sqla + time_range ---
    # Missing or null granularity_sqla causes 'Datetime column not provided'
    # and 'Chart has no query context saved' errors (most frequent failures).
    TIME_BASED_TYPES = {
        "echarts_timeseries_line", "echarts_timeseries_bar", "echarts_area",
        "echarts_timeseries_scatter", "mixed_timeseries", "waterfall",
        "big_number", "big_number_total",
    }
    if actual_viz in TIME_BASED_TYPES:
        if not fixed.get("granularity_sqla"):  # catches None, "", missing
            time_col = fixed.get("x_axis") or "ds"
            time_grain = fixed.pop("time_grain_sqla", None) or "P1D"
            fixed["granularity_sqla"] = {"time_column": time_col, "time_grain": time_grain}
        if not fixed.get("time_range"):
            fixed["time_range"] = "No filter"

    # --- Fix 14: Superset 6.x — all remaining string metrics → AdHocMetricObject ---
    # ALL chart types in Superset 6.x require ad-hoc metric objects.
    # Plain strings like 'SUM(sales)' in 'metrics' array are not accepted.
    # Exception: bare 'count' is a built-in metric, not a column reference.
    if actual_viz not in NO_METRICS_TYPES and "metrics" in fixed:
        metrics_list = fixed["metrics"]
        if isinstance(metrics_list, list):
            for i, m in enumerate(metrics_list):
                if isinstance(m, str) and m.strip().lower() != "count":
                    fixed["metrics"][i] = _build_adhoc_metric_from_string(m)
    # Also handle secondary metrics (mixed_timeseries uses metrics_b)
    if actual_viz not in NO_METRICS_TYPES and "metrics_b" in fixed:
        metrics_list = fixed["metrics_b"]
        if isinstance(metrics_list, list):
            for i, m in enumerate(metrics_list):
                if isinstance(m, str) and m.strip().lower() != "count":
                    fixed["metrics_b"][i] = _build_adhoc_metric_from_string(m)

    # --- Fix 14a: Axis fields → AdHocMetricObject ---
    # Scatter/bubble x, y, size, series values like 'MAX(SP.POP.TOTL)'
    # must be ad-hoc metric objects in Superset 6.x, not plain strings.
    for axis in ["x", "y", "size", "size_metric", "series"]:
        if axis in fixed and isinstance(fixed[axis], str):
            s = fixed[axis].strip().lower()
            if s == "count":
                continue
            agg, col_name = _parse_string_metric(fixed[axis])
            if agg != "AVG" or col_name != fixed[axis]:
                fixed[axis] = _build_adhoc_metric_from_string(fixed[axis])

    # --- Fix 16: Universal aggregate + expressionType + label for ALL metric dicts ---
    # Uses .get() instead of 'in' to catch None, "", 0 (all falsy).
    # Covers singular metric, plural metrics, metrics_b, timeseries_limit_metric.
    for field in ["metric", "timeseries_limit_metric"]:
        if field in fixed and isinstance(fixed[field], dict):
            if not fixed[field].get("aggregate"):
                fixed[field]["aggregate"] = "AVG"
            if not fixed[field].get("expressionType"):
                fixed[field]["expressionType"] = "SIMPLE"
            if not fixed[field].get("label"):
                agg = fixed[field].get("aggregate", "AVG")
                col = fixed[field].get("column", {}).get("column_name", "?")
                fixed[field]["label"] = f"{agg}({col})"
    for metric_field in ["metrics", "metrics_b"]:
        if metric_field in fixed and isinstance(fixed[metric_field], list):
            for m in fixed[metric_field]:
                if isinstance(m, dict):
                    if not m.get("aggregate"):
                        m["aggregate"] = "AVG"
                    if not m.get("expressionType"):
                        m["expressionType"] = "SIMPLE"
                    if not m.get("label"):
                        agg = m.get("aggregate", "AVG")
                        col = m.get("column", {}).get("column_name", "?")
                        m["label"] = f"{agg}({col})"

    # --- Fix 18: Universal label for groupby/orderby dict entries ---
    # Superset 6.x frontend iterates over groupby/orderby expecting .label
    # on each item. Dict entries without label cause 'can't access property'.
    for field in ["groupby", "orderby"]:
        if field in fixed and isinstance(fixed[field], list):
            for item in fixed[field]:
                if isinstance(item, dict) and not item.get("label"):
                    col = item.get("column", {}).get("column_name", "")
                    item["label"] = col or "unknown"

    return fixed


def validate_datasource_compatibility(
    viz_type: str,
    params: Dict[str, Any],
    dataset_columns: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    """
    Validate that the datasource and params are compatible for the viz type.
    
    Checks datasource requirements like:
    - world_map needs entity field
    - bubble_v2 needs x, y, size fields
    - heatmap_v2 needs x_axis and groupby
    - sunburst/treemap need groupby or columns for hierarchy
    - time series charts prefer temporal x_axis
    
    Returns list of error messages. Empty list means compatible.
    """
    errors: List[str] = []
    reqs = DATASOURCE_REQUIREMENTS.get(viz_type)
    
    if not reqs:
        return errors
    
    required_fields = reqs.get("required", [])
    optional_fields = reqs.get("optional", [])
    description = reqs.get("description", "")
    
    # Check required fields
    for field in required_fields:
        if field == "entity":
            if not params.get("entity"):
                errors.append(
                    f"Chart '{viz_type}' requires 'entity' field. "
                    f"Add: 'entity': 'country_code' (or geographic identifier column). "
                    f"Dataset columns: {[c.get('column_name') for c in dataset_columns] if dataset_columns else 'unknown'}"
                )
        elif field == "groupby":
            if "groupby" not in params:
                errors.append(
                    f"Chart '{viz_type}' requires 'groupby' field. "
                    f"Add: 'groupby': '<column_name>' (dimension to categorize by)."
                )
        elif field in params:
            val = params[field]
            if isinstance(val, str) and not val.strip():
                errors.append(f"Chart '{viz_type}' field '{field}' is empty.")
            elif isinstance(val, list) and len(val) == 0:
                errors.append(f"Chart '{viz_type}' field '{field}' is an empty list.")
        else:
            errors.append(
                f"Chart '{viz_type}' requires field '{field}'. "
                f"Add it to params. {description}"
            )
    
    # Check optional fields for empty/missing
    for field in optional_fields:
        if field == "entity":
            if "entity" not in params and viz_type == "world_map":
                pass  # world_map has entity in required
        elif field in params:
            val = params[field]
            if isinstance(val, str) and not val.strip():
                errors.append(f"Chart '{viz_type}' field '{field}' is empty.")
    
    # Check temporal x_axis for time series charts
    if reqs.get("x_axis_temporal") and params.get("x_axis"):
        if dataset_columns:
            x_axis_lower = params["x_axis"].lower()
            temporal_found = False
            for col in dataset_columns:
                col_name = col.get("column_name", "").lower()
                col_type = str(col.get("type", "")).lower()
                if col_name == x_axis_lower:
                    is_temporal = any(
                        k in col_type for k in ["date", "time", "datetime", "timestamp", "temporal"]
                    )
                    if is_temporal:
                        temporal_found = True
                    else:
                        errors.append(
                            f"Chart '{viz_type}' uses x_axis='{params['x_axis']}' but it's not a date/time column. "
                            f"Found columns: {[c.get('column_name') for c in dataset_columns]}"
                        )
                    break
            if not temporal_found and x_axis_lower not in [c.get("column_name", "").lower() for c in dataset_columns]:
                errors.append(
                    f"Chart '{viz_type}' uses x_axis='{params['x_axis']}' which doesn't exist in dataset. "
                    f"Available columns: {[c.get('column_name') for c in dataset_columns]}"
                )
    
    # Check big_number trendline temporal requirement
    if viz_type == "big_number" and params.get("show_trend_line", False):
        if not params.get("x_axis"):
            errors.append(
                "Chart 'big_number' with trendline enabled requires x_axis field. "
                "Add: 'x_axis': '<temporal_column_name>'"
            )
        elif dataset_columns:
            x_axis_lower = params["x_axis"].lower()
            temporal_found = False
            for col in dataset_columns:
                col_name = col.get("column_name", "").lower()
                col_type = str(col.get("type", "")).lower()
                if col_name == x_axis_lower:
                    is_temporal = any(
                        k in col_type for k in ["date", "time", "datetime", "timestamp", "temporal"]
                    )
                    if is_temporal:
                        temporal_found = True
                    else:
                        errors.append(
                            f"Chart 'big_number' with trendline uses x_axis='{params['x_axis']}' but it's not a date/time column. "
                            f"Add a temporal column like 'order_date' or 'created_at'."
                        )
                    break
            if not temporal_found:
                errors.append(
                    f"Chart 'big_number' with trendline uses x_axis='{params['x_axis']}' which doesn't exist in dataset. "
                    f"Available columns: {[c.get('column_name') for c in dataset_columns]}"
                )
    
    return errors


def format_error_summary(errors: List[str]) -> str:
    """Format validation errors into a readable string."""
    if not errors:
        return "No errors found. Parameters are valid."
    lines = [f"Found {len(errors)} error(s):"]
    for i, err in enumerate(errors, 1):
        lines.append(f"  {i}. {err}")
    return "\n".join(lines)
