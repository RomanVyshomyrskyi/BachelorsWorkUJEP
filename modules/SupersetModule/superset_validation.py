"""
Superset chart parameter validation and auto-fixing.

Prevents 'e.column is undefined' and 'Data error' frontend errors by catching
and fixing malformed chart params before they are sent to the Superset API.

The core issue: Superset's frontend expects specific nested structures
for metrics and axis values. When these structures are malformed, the
frontend crashes with TypeError when trying to access e.column.columnName.

Architecture Overview:
    This module implements a two-phase pipeline for chart parameter hygiene:

    Phase 1 — Validation (`validate_chart_params`):
        Checks chart params against the expected format for each viz_type.
        Uses 10 category sets that define which metric format each viz_type expects:
          1. SINGULAR_STRING_METRIC_TYPES  — single string metric ("metric": "count")
          2. SINGULAR_ADHOC_METRIC_TYPES   — single AdHocMetricObject dict
          3. STRING_METRICS_ARRAY_TYPES    — array of string metrics
          4. ADHOC_METRICS_ARRAY_TYPES     — array of AdHocMetricObject dicts
          5. MIXED_METRICS_TYPES           — accepts both strings and objects in array
          6. NO_METRICS_TYPES              — no metric/metrics field at all
          7. ENTITY_REQUIRED_TYPES         — needs 'entity' field (world_map)
          8. SANKEY_TYPES                  — needs source/target fields
          9. DATASOURCE_REQUIREMENTS       — needs specific column types
         10. TIME_BASED_TYPES              — needs granularity_sqla + time_range
        Checks duplicate labels, nested axis structure, and required fields.

    Phase 2 — Auto-Fix (`auto_fix_chart_params`):
        Applies 18+ fix rules in sequence to correct common parameter mistakes:
          Fix 0:  datasource_id type conversion (str → int)
          Fix 1:  entity field for map types
          Fix 1.5: Sankey cycle-breaking SQL hint
          Fix 2:  Pie/waterfall groupby normalization (list → string)
          Fix 3:  Pie/waterfall metrics array → metric object
          Fix 3.1: Singular string types metrics array → metric string
          Fix 4:  String metrics → AdHocMetricObject conversion (except bare 'count')
          Fix 5:  Scatter/bubble axis nesting correction (flat → nested column)
          Fix 6:  String array type malformed object fix
          Fix 7:  AdHocMetricObject required fields completion
          Fix 8:  AdHoc metrics array fix
          Fix 9:  Mixed metrics type fix
          Fix 11: Universal groupby array normalization (string → [string])
          Fix 12: Big number time config defaults
          Fix 13: Universal null column_name replacement
          Fix 13b: Universal orderby cleanup (drop null entries)
          Fix 13c: Columns/all_columns null entry cleanup
          Fix 14: String metrics → AdHocMetricObject in arrays
        Fix 14a: Axis fields → AdHocMetricObject
         Fix 15: Strip invalid fields (type, data_type) from metric column objects
         Fix 16: Universal aggregate/expressionType/label completion
         Fix 18: Universal label for groupby/orderby/columns dict entries

    The auto-fixer is iterative and covers multiple metric fields (metric, metrics,
    metrics_b, timeseries_limit_metric) plus axis fields (x, y, size, series).

Categorization matches ACTUAL working chart formats from Superset's own examples.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Viz type categories – matches ACTUAL working chart formats ────────────────
# These 10 category sets classify every Superset chart viz_type by the
# metric format it expects. Used by validate_chart_params to check format
# correctness and by auto_fix_chart_params to apply the right conversions.

# Category 1: Chart types that expect a SINGLE STRING metric.
#   "metric": "count"  or  "metric": "SUM(sales)"
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

# Category 2: Chart types that expect a SINGLE AdHocMetricObject dict.
#   "metric": {"aggregate": "SUM", "column": {...}}
SINGULAR_ADHOC_METRIC_TYPES: set = {
    "pie",
    "waterfall",
}

# Category 3: Chart types that expect an ARRAY of string metrics.
#   "metrics": ["count", "SUM(col)"]
STRING_METRICS_ARRAY_TYPES: set = {
    "echarts_timeseries_line",
    "echarts_timeseries_bar",
    "echarts_area",
    "echarts_timeseries_scatter",
    "bubble_v2",
    "box_plot",
    # REMOVED: "parallel"  — chart plugin not registered on Superset 6.1.0
}

# Category 4: Chart types that expect an ARRAY of AdHocMetricObject dicts.
#   "metrics": [{"aggregate": "SUM", ...}]
ADHOC_METRICS_ARRAY_TYPES: set = {
    "mixed_timeseries",
    "pivot_table_v2",
}

# Category 5: Chart types that accept BOTH strings and objects in the metrics array.
MIXED_METRICS_TYPES: set = {
    "radar",
}

# Category 6: Chart types that have NO metric/metrics field at all.
NO_METRICS_TYPES: set = {
    "histogram_v2",
    "gantt_chart",
}

# Category 7: Requires an 'entity' field for geographic mapping.
ENTITY_REQUIRED_TYPES: set = {
    "world_map",
}

# Category 8: Requires source/target fields and validates DAG structure.
SANKEY_TYPES: set = {
    "sankey_v2",
}

# Category 9: Viz types that need specific datasource column types for compatibility.
#   Maps viz_type → {required, optional, x_axis_temporal, description}
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
    # REMOVED: "parallel" — chart plugin not registered on Superset 6.1.0
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


# Category 10: Chart types that need granularity_sqla + time_range.
#   All time-based charts plus big_number (which can show trend lines).
TIME_BASED_TYPES: set = {
    "echarts_timeseries_line", "echarts_timeseries_bar", "echarts_area",
    "echarts_timeseries_scatter", "mixed_timeseries", "waterfall",
    "big_number", "big_number_total",
}


# ── Helpers ──────────────────────────────────────────────────────────────────


INVALID_METRIC_STRINGS: set = {
    "undefined", "null", "none", "",
}


def _is_adhoc_metric_object(val: Any) -> bool:
    """
    Check if a value is a properly formatted AdHocMetricObject dict.

    Description:
        Validates that a dict has the required nested structure of an AdHocMetricObject:
        a 'column' key containing a dict with a non-empty 'column_name' string.

    Args:
        val: Value to check.

    Returns:
        True if val is a dict with valid column.column_name structure, False otherwise.
    """
    # Step 1: Must be a dict — non-dict values (strings, None, lists) are never valid
    if not isinstance(val, dict):
        return False
    # Step 2: Must have a 'column' key whose value is itself a dict
    column = val.get("column")
    if not isinstance(column, dict):
        return False
    # Step 3: The nested 'column_name' must exist and be a non-empty string
    column_name = column.get("column_name")
    return bool(column_name and isinstance(column_name, str))


def _is_string_metric(val: Any) -> bool:
    """
    Check if a value is a valid string metric like 'count', 'SUM(col)', etc.

    Description:
        Returns True if val is a non-empty, non-whitespace string that could
        represent a metric (e.g. "count", "SUM(sales)", "AVG(price)").

    Args:
        val: Value to check.

    Returns:
        True if val is a non-empty string, False otherwise.
    """
    # Step 1: Must be a string type
    if not isinstance(val, str):
        return False
    # Step 2: Must have non-whitespace content (empty/whitespace strings are invalid)
    return val.strip() != ""


def _parse_string_metric(metric_str: str) -> Tuple[str, str]:
    """
    Parse a string metric like 'SUM(sales)' or 'AVG(price)' into (aggregate, column_name).

    Description:
        Extracts the aggregation function and column name from a metric string.
        Handles special case 'count' and standard SQL expressions.
        Falls back to ('AVG', metric_str) for unrecognized patterns.

    Args:
        metric_str: Metric string like 'SUM(sales)', 'AVG(price)', or 'count'.

    Returns:
        Tuple of (aggregate, column_name). Returns ('COUNT', 'count') for 'count'.
        Returns ('AVG', metric_str) as fallback for unrecognized patterns.
    """
    metric_str = metric_str.strip()
    # Step 1: Special case — bare 'count' is a built-in Superset metric (COUNT(*))
    if metric_str.lower() == "count":
        return ("COUNT", "count")

    # Step 2: Match SQL expression format: SUM(column), AVG(column), etc.
    #   Uses case-insensitive regex to extract function name and column inside parens.
    match = re.match(
        r"^(SUM|AVG|MIN|MAX|COUNT|COUNT_DISTINCT)\s*\(\s*(.+?)\s*\)$",
        metric_str,
        re.IGNORECASE,
    )
    if match:
        return (match.group(1).upper(), match.group(2).strip())

    # Step 3: Fallback — treat entire string as column name with AVG aggregation
    return ("AVG", metric_str)


def _build_adhoc_metric_from_string(metric_str: str) -> Dict[str, Any]:
    """
    Convert a string metric like 'SUM(sales)' to an AdHocMetricObject.

    Description:
        Parses a string metric and constructs a properly nested AdHocMetricObject
        dict with aggregate, column, expressionType, and label fields.
        Handles both 'SUM(sales)' and 'sum__SP_POP_TOTL' (Superset internal) formats.

    Args:
        metric_str: String metric like 'SUM(sales)', 'AVG(price)', or 'sum__sales'.

    Returns:
        Dict formatted as an AdHocMetricObject with all required fields.

    Example:
        >>> _build_adhoc_metric_from_string("SUM(sales)")
        {'aggregate': 'SUM', 'column': {'column_name': 'sales'}, 'expressionType': 'SIMPLE', 'label': 'SUM(sales)'}
    """
    # Step 0: Handle Superset internal format 'sum__column_name', 'avg__col', etc.
    #   These are already aggregated metric names created by Superset's query engine.
    #   The prefix is the aggregate function (lowercase), followed by '__', then column name.
    internal_match = re.match(r'^(sum|avg|min|max|count|count_distinct)__(.+)$', metric_str.strip(), re.IGNORECASE)
    if internal_match:
        agg = internal_match.group(1).upper()
        col_name = internal_match.group(2)
        return {
            "aggregate": agg,
            "column": {"column_name": col_name},
            "expressionType": "SIMPLE",
            "label": f"{agg}({col_name})",
        }
    # Step 1: Parse the metric string to extract aggregate function and column name
    #   "SUM(sales)" → agg="SUM", col_name="sales"
    #   "AVG(price)" → agg="AVG", col_name="price"
    agg, col_name = _parse_string_metric(metric_str)

    # Step 2: Build the AdHocMetricObject dict with proper nested structure.
    #   The frontend requires this exact shape — flat alternatives cause
    #   'e.column is undefined' errors.
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

    Description:
        Performs comprehensive validation of chart parameters against the expected
        format for each viz type. Checks metric format, required fields, axis
        structure, and duplicate labels. Returns an empty list if params are valid.

    Args:
        viz_type: The Superset viz_type string (e.g. "echarts_timeseries_line", "pie").
        params: Chart params dict to validate.

    Returns:
        List of error message strings. Empty list means params are valid.

    Example:
        >>> errors = validate_chart_params("pie", {"groupby": ["product_line"]})
        >>> errors  # Missing 'metric' field
        ["Chart 'pie' is missing 'metric' field. Add: 'metric': 'count' (or 'SUM(column_name)')."]
    """
    errors: List[str] = []
    actual_viz = viz_type

    # ═══ Phase 1: Field existence checks (entity, source/target) ═══

    # Check 1: world_map needs an 'entity' field for geographic mapping resolution.
    #   Without this, Superset can't map data points to geographic regions.
    if actual_viz in ENTITY_REQUIRED_TYPES:
        if not params.get("entity"):
            errors.append(
                f"Chart '{actual_viz}' is missing required 'entity' field. "
                f"Add: 'entity': 'country_code' (or the column with country identifiers)."
            )

    # Check 1.5: Sankey charts need source/target to define flow between nodes.
    #   Missing either causes the DAG to be incomplete — no edges to render.
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

    # ═══ Phase 2: Metric format validation per viz type category ═══
    #   Each viz_type belongs to exactly one category that specifies the expected
    #   format (singular vs. array, string vs. AdHocMetricObject).

    if actual_viz in SINGULAR_STRING_METRIC_TYPES:
        # Category 1: Expects a single string metric.
        #   Valid: "metric": "count", "metric": "SUM(sales)"
        #   Invalid: "metrics" array, null metric, placeholder strings like "undefined"
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
            # Check for null metric value
            if metric_val is None:
                errors.append(
                    f"Chart '{actual_viz}' has null 'metric'. "
                    f"Set it to 'count' or 'SUM(column_name)'."
                )
            elif _is_string_metric(metric_val):
                ms = metric_val.strip().lower()
                # Check for invalid placeholder strings
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
        # Category 6: table, histogram_v2, gantt_chart — should NOT have metric/metrics
        if "metric" in params or "metrics" in params:
            errors.append(
                f"Chart '{actual_viz}' should not have a 'metric' or 'metrics' field."
            )

    # ═══ Phase 3: Duplicate label detection ═══
    #   Superset frontend identifies metrics/columns by their labels, and duplicate
    #   labels cause ambiguity in rendering. We check 'metric', 'metrics' array,
    #   and 'groupby' for overlapping labels.
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

    # ═══ Phase 4: Scatter/bubble axis nesting validation ═══
    #   These charts use structured x/y axis objects that must have
    #   {"column": {"column_name": "..."}} nesting — flat structures cause
    #   'e.column is undefined' in the Superset frontend.
    #   We detect two common anti-patterns:
    #     a) "column_name" at the top level instead of inside "column"
    #     b) "column" as a string instead of a dict with "column_name"
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

    # ═══ Phase 5: Required fields for AdHocMetricObjects in singular metric types ═══
    #   Pie/waterfall charts require a full AdHocMetricObject with both
    #   'aggregate' and 'expressionType' fields. Missing either causes
    #   the chart to fail silently or error on the frontend.
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
    Auto-fix common parameter mistakes in chart params.

    Description:
        Applies a series of corrections to chart params to fix the most common
        issues that cause Superset frontend errors (e.g., 'e.column is undefined',
        'Data error', 'Cannot compile Column object'). Handles metric format
        conversion, groupby normalization, null column replacement, and more.

    Args:
        viz_type: The Superset viz_type string.
        params: Chart params dict with potential issues.

    Returns:
        A new params dict with corrections applied.

    Note:
        Always call validate_chart_params() after this function to check for
        remaining errors that couldn't be auto-fixed.

    Fixes applied (in order):
        Fix 0:  datasource_id type conversion (str -> int)
        Fix 1:  entity field for map types
        Fix 1.5: cycle-breaking hint for Sankey charts
        Fix 2:  Pie/waterfall groupby normalization (list -> string)
        Fix 3:  Pie/waterfall metrics array -> metric object
        Fix 3.1: Singular string metric types: metrics array -> metric string
        Fix 4:  String metrics -> AdHocMetricObject conversion
        Fix 5:  Scatter/bubble axis nesting correction
        Fix 6:  String array type object fix
        Fix 7:  AdHocMetricObject required fields completion
        Fix 8:  AdHoc metrics array fix
        Fix 9:  Mixed metrics type fix
        Fix 11: Universal groupby array normalization
        Fix 12: Big number time config for dashboard rendering
        Fix 13: Universal null column_name replacement
        Fix 13b: Universal orderby cleanup (drop null entries)
        Fix 13c: Columns/all_columns null entry cleanup
        Fix 17: Time series + big_number granularity/time_range defaults
        Fix 14: String metrics -> AdHocMetricObject in arrays
        Fix 14a: Axis fields -> AdHocMetricObject
        Fix 16: Universal aggregate/expressionType/label completion
        Fix 18: Universal label for groupby/orderby/columns dict entries

        Example:
            >>> bad_params = {"groupby": "product_line", "metrics": ["SUM(sales)"], "metric": None}
            >>> fixed = auto_fix_chart_params("echarts_timeseries_line", bad_params)
            >>> fixed["groupby"]
            ['product_line']
            >>> fixed["metric"]
            {'aggregate': 'AVG', 'column': {'column_name': 'count'}, 'expressionType': 'SIMPLE', 'label': 'AVG(count)'}
    """
    # Deep copy via JSON round-trip — ensures no shared references with the
    # original params dict, preventing unintended mutations.
    fixed = json.loads(json.dumps(params))
    actual_viz = viz_type

    # ═══ Fix 0b: Flatten nested 'params' key (would cause double-nesting) ═══
    #   If the user's config already has a 'params' key, extract its content
    #   and merge into the top-level params. This prevents nested params like
    #   {"params": {"params": {...}}} when the API is called.
    if "params" in fixed:
        nested = fixed["params"]
        if isinstance(nested, dict):
            # Merge inner params into outer, giving inner priority
            for k, v in nested.items():
                if k not in fixed or fixed[k] is None:
                    fixed[k] = v
            del fixed["params"]

    # ═══ Fix 0: Ensure datasource_id is always present and is an integer ═══
    #   Superset expects datasource_id as int, but sometimes it comes as str
    #   from JSON parsing or external API responses. The int conversion prevents
    #   type mismatch errors when comparing or routing datasource references.
    if "datasource_id" in fixed and isinstance(fixed.get("datasource_id"), str):
        try:
            fixed["datasource_id"] = int(fixed["datasource_id"])
        except (ValueError, TypeError):
            pass

    # ═══ Fix 1: Entity field for map types ═══
    #   World map uses 'entity' to identify the geographic column (e.g., country_code).
    #   Default to "country_code" which is the most common column name.
    if actual_viz in ENTITY_REQUIRED_TYPES:
        if not fixed.get("entity"):
            fixed["entity"] = "country_code"

    # ═══ Fix 1.5: Sankey charts — add cycle-breaking SQL hint ═══
    #   Sankey diagrams require acyclic graphs. If source == target creates a cycle,
    #   the chart fails. We inject a SQL hint that the user can add to their dataset
    #   to break cycles (AND source_col < target_col).
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

    # ═══ Fix 2: Pie/waterfall — groupby must be string, not array ═══
    #   These chart types expect a single dimension column, not a list.
    #   If a list is provided, we pick the first element.
    if actual_viz in SINGULAR_ADHOC_METRIC_TYPES and "groupby" in fixed:
        groupby = fixed["groupby"]
        if isinstance(groupby, list) and len(groupby) == 1:
            fixed["groupby"] = groupby[0]
        elif isinstance(groupby, list) and len(groupby) > 1:
            fixed["groupby"] = groupby[0]
        elif not isinstance(groupby, str):
            fixed["groupby"] = ""

    # ═══ Fix 3: Pie/waterfall — metrics array → metric object ═══
    #   If the user mistakenly put metrics in an array (plural), move the
    #   first element into the singular 'metric' field and delete the array.
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

    # ═══ Fix 3.1: SINGULAR_STRING_METRIC_TYPES — metrics array → metric string ═══
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

    # ═══ Fix 4: Singular metric types — string metric → AdHocMetricObject ═══
    #   SINGULAR_ADHOC_METRIC_TYPES (pie, waterfall) MUST always have ad-hoc objects.
    #   SINGULAR_STRING_METRIC_TYPES accept strings but should convert for Superset 6.x,
    #   EXCEPT bare 'count' — which is a built-in metric the frontend understands natively.
    if actual_viz in SINGULAR_ADHOC_METRIC_TYPES:
        if "metric" in fixed and _is_string_metric(fixed["metric"]):
            fixed["metric"] = _build_adhoc_metric_from_string(fixed["metric"])
    # SINGULAR_STRING_METRIC_TYPES (big_number, funnel, etc.) accept strings,
    # but should still convert to ad-hoc for Superset 6.x — except bare 'count'.
    if actual_viz in SINGULAR_STRING_METRIC_TYPES:
        if "metric" in fixed and _is_string_metric(fixed["metric"]):
            # Bare 'count' is a built-in Superset metric — leave it as string
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

    # granuarity_sqla is now handled universally by Fix 17 below.
    # Fix 10 has been consolidated — removed dead _needs_temporal_check flag.
    
    # --- Fix 11: Universal — groupby must be array for all chart types ---
    # Superset 6.x dashboard rendering expects groupby as array everywhere.
    if "groupby" in fixed and isinstance(fixed["groupby"], str):
        fixed["groupby"] = [fixed["groupby"]] if fixed["groupby"] else []

    # --- Fix 12: big_number — ensure time config for dashboard rendering ---
    if actual_viz == "big_number":
        if "time_range" not in fixed:
            fixed["time_range"] = "100 years ago : now"
        if "adhoc_filters" not in fixed:
            fixed["adhoc_filters"] = []

    # ═══ Fix 13: General null column_name fix for ALL metric types ═══
    #   Prevents "Cannot compile Column object until its 'name' is assigned"
    #   by replacing null column_name with first available groupby or 'count'.
    #   This is the most critical fix — null column references cause the
    #   frontend to crash with an unhelpful error message.
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
    if actual_viz in TIME_BASED_TYPES:
        if not fixed.get("granularity_sqla"):  # catches None, "", missing
            time_col = fixed.get("x_axis") or "ds"
            fixed["granularity_sqla"] = time_col
        if not fixed.get("time_grain_sqla"):
            fixed["time_grain_sqla"] = "P1D"
        if not fixed.get("time_range"):
            fixed["time_range"] = "No filter"

    # --- Fix 14b: Normalize query_context.query structure for Superset 5.x/6.x ---
    # query_context uses 'name' for column names but frontend expects 'column_name'.
    # Also add 'label' to all column/dimension dict entries to prevent 'can't access property' errors.
    if "query_context" in fixed and "query" in fixed["query_context"]:
        qc_query = fixed["query_context"]["query"]
        for col_field in ["columns"]:
            if col_field in qc_query and isinstance(qc_query[col_field], list):
                for col_entry in qc_query[col_field]:
                    if isinstance(col_entry, dict):
                        col = col_entry.get("column", {})
                        if isinstance(col, dict) and "name" in col and "column_name" not in col:
                            col["column_name"] = col.pop("name")
                        if isinstance(col, dict) and col.get("column_name") and not col.get("label"):
                            col["label"] = col["column_name"]
        for item in ["groupby", "metrics"]:
            if item in qc_query and isinstance(qc_query[item], list):
                for i, entry in enumerate(qc_query[item]):
                    if isinstance(entry, dict) and "column" in entry:
                        col = entry["column"]
                        if isinstance(col, dict) and "name" in col and "column_name" not in col:
                            col["column_name"] = col.pop("name")
                        if isinstance(col, dict) and col.get("column_name") and not col.get("label"):
                            col["label"] = col["column_name"]
                    elif isinstance(entry, dict) and not entry.get("label"):
                        entry["label"] = entry.get("column", {}).get("column_name", "unknown")

    # --- Fix 14: Superset 6.x — all remaining string metrics → AdHocMetricObject ---
    # ALL chart types in Superset 6.x require ad-hoc metric objects.
    # Plain strings like 'SUM(sales)' in 'metrics' array are not accepted.
    # Exception: bare 'count' is a built-in metric, not a column reference.
    # SKIP if query_context already has metrics (Superset 5.x style — don't mix formats)
    has_query_context_metrics = "query_context" in fixed and "query" in fixed.get("query_context", {}) and "metrics" in fixed.get("query_context", {}).get("query", {})
    if actual_viz not in NO_METRICS_TYPES and "metrics" in fixed and not has_query_context_metrics:
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
    # Also handle query_context.query.metrics (Superset 5.x/6.x query engine format)
    if actual_viz not in NO_METRICS_TYPES and has_query_context_metrics:
        qc_metrics = fixed["query_context"]["query"]["metrics"]
        if isinstance(qc_metrics, list):
            for i, m in enumerate(qc_metrics):
                if isinstance(m, str) and m.strip().lower() != "count":
                    qc_metrics[i] = _build_adhoc_metric_from_string(m)

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

   # --- Fix 15: Strip invalid fields from metric column objects ---
    # The 'type' field in column objects (e.g., "type": "DOUBLE PRECISION") causes
    # SQLAlchemy "Cannot compile Column object until its 'name' is assigned" errors.
    # Superset's chart API expects column objects to only have 'column_name', not
    # full column metadata. Also normalize expressionType to SIMPLE for column refs.
    _CLEANED_METRICS = 0
    def _clean_metric_column(metric_obj):
        nonlocal _CLEANED_METRICS
        if isinstance(metric_obj, dict) and "column" in metric_obj:
            col = metric_obj["column"]
            if isinstance(col, dict):
                _removed = []
                for key in ["type", "data_type", "verbose_name", "is_dttm", "id", "primary_key"]:
                    if key in col:
                        _removed.append(key)
                        del col[key]
                if _removed:
                    _CLEANED_METRICS += 1
                    logger.warning(f"Fix 15: Stripped invalid column fields {_removed} from metric: {metric_obj.get('label', '?')}")
                    print(f"Fix 15: Stripped {_removed} from metric {metric_obj.get('label', '?')}", flush=True)
            if metric_obj.get("expressionType") == "SQL" and metric_obj.get("aggregate"):
                if metric_obj["expressionType"] != "SIMPLE":
                    metric_obj["expressionType"] = "SIMPLE"
                    _CLEANED_METRICS += 1
                    logger.warning(f"Fix 15: Normalized expressionType SQL->SIMPLE for metric: {metric_obj.get('label', '?')}")
                    print(f"Fix 15: Normalized expressionType for {metric_obj.get('label', '?')}", flush=True)
                if "metricType" in metric_obj:
                    del metric_obj["metricType"]
                    _CLEANED_METRICS += 1
    
    for field in ["metric", "timeseries_limit_metric"]:
        if field in fixed and isinstance(fixed[field], dict):
            _clean_metric_column(fixed[field])
    for metric_field in ["metrics", "metrics_b"]:
        if metric_field in fixed and isinstance(fixed[metric_field], list):
            for m in fixed[metric_field]:
                if isinstance(m, dict):
                    _clean_metric_column(m)
    
    if _CLEANED_METRICS > 0:
        logger.info(f"Fix 15: cleaned {_CLEANED_METRICS} metric column issues")
        print(f"Fix 15: Total cleaned {_CLEANED_METRICS} issues", flush=True)

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

    # --- Fix 18: Universal label for groupby/orderby/columns dict entries ---
    # Superset 6.x frontend iterates over groupby/orderby/columns expecting
    # .label on each item. Dict entries without label cause 'can't access property'.
    for field in ["groupby", "orderby", "columns", "all_columns"]:
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

    Description:
        Checks datasource-level compatibility requirements by cross-referencing
        chart params against required/optional fields and column data types.
        Used as a secondary check after metric format validation.

    Args:
        viz_type: The Superset viz_type string (e.g. "bubble_v2", "heatmap_v2").
        params: Chart params dict to validate.
        dataset_columns: Optional list of column dicts from the dataset, used
            to verify column existence and data types (e.g., temporal vs. numeric).

    Returns:
        List of error message strings. Empty list means compatible.

    Checks:
        - world_map needs entity field
        - bubble_v2 needs x, y, size fields
        - heatmap_v2 needs x_axis and groupby
        - sunburst/treemap need groupby or columns for hierarchy
        - time series charts prefer temporal x_axis
        - big_number trendline needs temporal x_axis

        Example:
            >>> cols = [{"column_name": "order_date", "type": "DATETIME"}]
            >>> errors = validate_datasource_compatibility("echarts_timeseries_line",
            ...     {"x_axis": "order_date", "granularity_sqla": "order_date"},
            ...     dataset_columns=cols)
            >>> errors  # x_axis is temporal — no errors
            []
            >>> errors = validate_datasource_compatibility("bubble_v2", {},
            ...     dataset_columns=cols)
            >>> errors  # bubble_v2 requires x, y, size fields
            ["Chart 'bubble_v2' requires field 'x'. ..."]
    """
    errors: List[str] = []
    # Step 1: Look up datasource requirements for this viz_type from the
    #   DATASOURCE_REQUIREMENTS dictionary (category 9).
    reqs = DATASOURCE_REQUIREMENTS.get(viz_type)

    if not reqs:
        return errors  # No specific requirements — chart is datasource-agnostic

    required_fields = reqs.get("required", [])
    optional_fields = reqs.get("optional", [])
    description = reqs.get("description", "")

    # Step 2: Validate each required field — must be present and non-empty.
    #   'entity' and 'groupby' have special handling because they can be
    #   string or array, and the error message needs to be domain-specific.
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
            # Field exists — check it's not empty/blank
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

    # Step 3: Check optional fields — only report if present but empty.
    for field in optional_fields:
        if field == "entity":
            if "entity" not in params and viz_type == "world_map":
                pass  # world_map has entity in required, redundant to check here
        elif field in params:
            val = params[field]
            if isinstance(val, str) and not val.strip():
                errors.append(f"Chart '{viz_type}' field '{field}' is empty.")

    # Step 4: For time series charts, verify x_axis is a temporal column.
    #   Non-temporal x_axis columns on time series charts produce misleading results
    #   since the chart expects date-based aggregation and range filtering.
    if reqs.get("x_axis_temporal") and params.get("x_axis"):
        if dataset_columns:
            x_axis_lower = params["x_axis"].lower()
            temporal_found = False
            for col in dataset_columns:
                col_name = col.get("column_name", "").lower()
                col_type = str(col.get("type", "")).lower()
                if col_name == x_axis_lower:
                    # Check if the column type contains any temporal keyword
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

    # Step 5: Big number with trendline enabled also needs a temporal x_axis.
    #   The trendline shows historical data, which requires a date field for ordering.
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
    """Format validation errors into a readable numbered list.

    Args:
        errors: List of error message strings from validate_chart_params.

    Returns:
        A human-readable summary string, or a success message if no errors.

        Example:
            >>> errors = ["Missing metric field", "Invalid groupby format"]
            >>> print(format_error_summary(errors))
            Found 2 error(s):
              1. Missing metric field
              2. Invalid groupby format
            >>> format_error_summary([])
            'No errors found. Parameters are valid.'
    """
    # Step 1: Handle the happy path — no errors means valid params.
    if not errors:
        return "No errors found. Parameters are valid."

    # Step 2: Build a numbered list of errors for easy scanning.
    lines = [f"Found {len(errors)} error(s):"]
    for i, err in enumerate(errors, 1):
        lines.append(f"  {i}. {err}")
    return "\n".join(lines)
