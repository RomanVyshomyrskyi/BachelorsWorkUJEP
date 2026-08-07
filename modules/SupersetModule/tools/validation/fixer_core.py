"""
Early auto-fix rules for chart parameters.

Applies fixes 0-12: type conversion, entity fields, groupby normalization,
metric conversions, null column fixes, and big_number time config.
"""

import json
import logging
from typing import Any, Dict

from .categories import (
    ADHOC_METRICS_ARRAY_TYPES,
    ENTITY_REQUIRED_TYPES,
    MIXED_METRICS_TYPES,
    NO_METRICS_TYPES,
    SANKEY_TYPES,
    SINGULAR_ADHOC_METRIC_TYPES,
    SINGULAR_STRING_METRIC_TYPES,
    STRING_METRICS_ARRAY_TYPES,
)
from .helpers import (
    _build_adhoc_metric_from_string,
    _is_adhoc_metric_object,
    _is_string_metric,
)

logger = logging.getLogger(__name__)


def apply_early_fixes(viz_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Apply fixes 0-12 to chart params.

    Covers: datasource_id, entity, sankey cycles, groupby normalization,
    metric conversions, axis nesting, null columns, big_number config.
    """
    fixed = json.loads(json.dumps(params))
    actual_viz = viz_type

    # Fix 0b: Remove nested 'params' key when query_context exists
    if "params" in fixed and "query_context" in fixed:
        del fixed["params"]
    elif "params" in fixed:
        nested = fixed["params"]
        if isinstance(nested, dict):
            for k, v in nested.items():
                if k not in fixed or fixed[k] is None:
                    fixed[k] = v
            del fixed["params"]

    # Fix 0: Ensure datasource_id is always an integer
    if "datasource_id" in fixed and isinstance(fixed.get("datasource_id"), str):
        try:
            fixed["datasource_id"] = int(fixed["datasource_id"])
        except (ValueError, TypeError):
            pass

    # Fix 1: Entity field for map types and bubble
    if actual_viz in ENTITY_REQUIRED_TYPES or actual_viz == "bubble_v2":
        if not fixed.get("entity"):
            if actual_viz == "bubble_v2":
                fixed["entity"] = "country_code"
            else:
                fixed["entity"] = "country_code"

    # Fix 1.5: Sankey charts — add cycle-breaking SQL hint
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

    # Fix 2: Pie/waterfall — groupby must be string, not array
    if actual_viz in SINGULAR_ADHOC_METRIC_TYPES and "groupby" in fixed:
        groupby = fixed["groupby"]
        if isinstance(groupby, list):
            fixed["groupby"] = groupby[0] if len(groupby) > 0 else ""
        elif not isinstance(groupby, str):
            fixed["groupby"] = ""

    # Fix 3: Pie/waterfall — metrics array -> metric object
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

    # Fix 3.1: SINGULAR_STRING_METRIC_TYPES — metrics array -> metric string
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

    # Fix 4: Singular metric types — string metric -> AdHocMetricObject
    if actual_viz in SINGULAR_ADHOC_METRIC_TYPES:
        if "metric" in fixed and _is_string_metric(fixed["metric"]):
            fixed["metric"] = _build_adhoc_metric_from_string(fixed["metric"])
    if actual_viz in SINGULAR_STRING_METRIC_TYPES:
        if "metric" in fixed and _is_string_metric(fixed["metric"]):
            if fixed["metric"].strip().lower() != "count":
                fixed["metric"] = _build_adhoc_metric_from_string(fixed["metric"])

    # Fix 5: Scatter/bubble — flat column_name -> nested column object
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
        # Fix 5b: Bubble — size field must be AdHocMetricObject (SIMPLE), not DIMENSION
        if actual_viz == "bubble_v2" and "size" in fixed:
            size_val = fixed["size"]
            # If already a valid SIMPLE metric, preserve it
            if isinstance(size_val, dict) and size_val.get("expressionType") == "SIMPLE" and "aggregate" in size_val:
                pass  # Already correct
            elif isinstance(size_val, str):
                col = size_val.strip()
                fixed["size"] = {
                    "aggregate": "AVG",
                    "column": {"column_name": col},
                    "expressionType": "SIMPLE",
                    "label": f"AVG({col})",
                }
            elif isinstance(size_val, dict):
                # Extract column name from any format
                if "column_name" in size_val and "column" not in size_val:
                    col = size_val["column_name"]
                elif "column" in size_val:
                    col_obj = size_val["column"]
                    if isinstance(col_obj, str):
                        col = col_obj
                    elif isinstance(col_obj, dict):
                        col = col_obj.get("column_name", "count")
                    else:
                        col = "count"
                else:
                    col = "count"
                agg = size_val.get("aggregate", "AVG") if isinstance(size_val.get("aggregate"), str) else "AVG"
                fixed["size"] = {
                    "aggregate": agg,
                    "column": {"column_name": col},
                    "expressionType": "SIMPLE",
                    "label": f"{agg}({col})",
                }

    # Fix 6: String array types — fix malformed objects only, keep strings
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

    # Fix 7: Ensure AdHocMetricObject has required fields
    if actual_viz in SINGULAR_ADHOC_METRIC_TYPES and "metric" in fixed:
        metric_val = fixed["metric"]
        if isinstance(metric_val, dict):
            if "column_name" in metric_val and "column" not in metric_val:
                column_name = metric_val.pop("column_name")
                metric_val["column"] = {"column_name": column_name}
            if metric_val.get("column", {}).get("column_name") is None:
                if "groupby" in metric_val:
                    metric_val["column"]["column_name"] = metric_val.pop("groupby")
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

    # Fix 8: AdHoc metrics array types — fix malformed objects only
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

    # Fix 9: Mixed metrics types — fix malformed objects only
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

    # Fix 11: Universal — groupby must be array for all chart types
    if "groupby" in fixed and isinstance(fixed["groupby"], str):
        fixed["groupby"] = [fixed["groupby"]] if fixed["groupby"] else []

    # Fix 12: big_number — ensure time config for dashboard rendering
    if actual_viz == "big_number":
        if "time_range" not in fixed:
            fixed["time_range"] = "100 years ago : now"
        if "adhoc_filters" not in fixed:
            fixed["adhoc_filters"] = []

    return fixed
