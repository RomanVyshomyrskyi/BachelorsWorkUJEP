"""
Universal auto-fix rules for chart parameters.

Applies fixes 13-18: null column replacement, orderby cleanup,
query_context normalization, string->AdHoc conversion, axis fields,
invalid field stripping, and label completion.
"""

import logging
from typing import Any, Dict, List

from .categories import (
    NO_METRICS_TYPES,
    TIME_BASED_TYPES,
)
from .helpers import (
    _build_adhoc_metric_from_string,
    _parse_string_metric,
)

logger = logging.getLogger(__name__)


def apply_universal_fixes(viz_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Apply universal fixes 13-18 to chart params.

    Covers: null columns, orderby cleanup, columns cleanup, time-based defaults,
    query_context normalization, string->AdHoc conversion, axis fields,
    invalid field stripping, aggregate/expressionType/label completion,
    and label completion for groupby/orderby/columns.
    """
    fixed = dict(params)  # Shallow copy — fixes modify in place
    actual_viz = viz_type

    # Fix 13: General null column_name fix for ALL metric types
    if actual_viz not in NO_METRICS_TYPES:
        fallback_col = _get_fallback_column(fixed)

        if "metric" in fixed and fixed["metric"] is None:
            fixed["metric"] = fallback_col
        elif "metric" in fixed and isinstance(fixed["metric"], dict):
            metric_col = fixed["metric"].get("column", {})
            if isinstance(metric_col, dict) and not metric_col.get("column_name"):
                fixed["metric"]["column"]["column_name"] = fallback_col
                if "expressionType" not in fixed["metric"]:
                    fixed["metric"]["expressionType"] = "SIMPLE"

        if "metrics" in fixed and isinstance(fixed["metrics"], list):
            for m in fixed["metrics"]:
                if isinstance(m, dict):
                    metric_col = m.get("column", {})
                    if isinstance(metric_col, dict) and not metric_col.get("column_name"):
                        m["column"]["column_name"] = fallback_col
                        if "expressionType" not in m:
                            m["expressionType"] = "SIMPLE"

        if "timeseries_limit_metric" in fixed:
            tlm = fixed["timeseries_limit_metric"]
            if tlm is None:
                fixed["timeseries_limit_metric"] = fallback_col
            elif isinstance(tlm, dict):
                col_name = tlm.get("column", {}).get("column_name")
                if col_name is None:
                    tlm.setdefault("column", {})["column_name"] = fallback_col

    # Fix 13b: Universal orderby cleanup
    if "orderby" in fixed and isinstance(fixed["orderby"], list):
        fixed["orderby"] = _clean_orderby(fixed["orderby"])

    # Fix 13c: columns / all_columns — drop null/empty entries
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

    # Fix 17: Time series + big_number — ensure granularity_sqla + time_range
    if actual_viz in TIME_BASED_TYPES:
        if not fixed.get("granularity_sqla"):
            time_col = fixed.get("x_axis") or "ds"
            fixed["granularity_sqla"] = time_col
        if not fixed.get("time_grain_sqla"):
            fixed["time_grain_sqla"] = "P1D"
        if not fixed.get("time_range"):
            fixed["time_range"] = "No filter"

    # Fix 14b: Normalize query_context.query structure for Superset 5.x/6.x
    if "query_context" in fixed and "query" in fixed["query_context"]:
        _fix_query_context(fixed["query_context"]["query"])

    # Fix 14: String metrics -> AdHocMetricObject in arrays
    _fix_string_metrics_in_arrays(fixed, actual_viz)

    # Fix 14c: Remove query_context.query.orderby
    if "query_context" in fixed and "query" in fixed["query_context"]:
        if "orderby" in fixed["query_context"]["query"]:
            del fixed["query_context"]["query"]["orderby"]

    # Fix 14a: Axis fields -> AdHocMetricObject
    _fix_axis_fields(fixed)

    # Fix 15: Strip invalid fields from metric column objects
    _fix_invalid_column_fields(fixed)

    # Fix 16: Universal aggregate + expressionType + label for ALL metric dicts
    _fix_metric_labels(fixed)

    # Fix 18: Universal label for groupby/orderby/columns dict entries
    _fix_groupby_labels(fixed)

    return fixed


def _get_fallback_column(params: Dict[str, Any]) -> str:
    """Get fallback column name from groupby or default to 'count'."""
    groupby = params.get("groupby")
    if isinstance(groupby, list) and len(groupby) > 0:
        return groupby[0]
    if isinstance(groupby, str) and groupby.strip():
        return groupby.strip()
    return "count"


def _clean_orderby(orderby: List) -> List:
    """Remove orderby entries with null/empty column references."""
    clean_orderby = []
    for entry in orderby:
        if isinstance(entry, list) and len(entry) >= 1:
            if entry[0] is None or (isinstance(entry[0], str) and not entry[0].strip()):
                continue
            clean_orderby.append(entry)
        elif isinstance(entry, dict):
            col_entry = entry.get("column")
            if col_entry is None or not isinstance(col_entry, dict):
                continue
            col_name = col_entry.get("column_name")
            if col_name is None or (isinstance(col_name, str) and not col_name.strip()):
                continue
            clean_orderby.append(entry)
    return clean_orderby


def _fix_query_context(qc_query: Dict) -> None:
    """Normalize query_context.query column names and add labels."""
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
            for entry in qc_query[item]:
                if isinstance(entry, dict) and "column" in entry:
                    col = entry["column"]
                    if isinstance(col, dict) and "name" in col and "column_name" not in col:
                        col["column_name"] = col.pop("name")
                    if isinstance(col, dict) and col.get("column_name") and not col.get("label"):
                        col["label"] = col["column_name"]
                elif isinstance(entry, dict) and not entry.get("label"):
                    entry["label"] = entry.get("column", {}).get("column_name", "unknown")


def _fix_string_metrics_in_arrays(fixed: Dict[str, Any], viz_type: str) -> None:
    """Convert string metrics to AdHocMetricObject in arrays."""
    has_qc_metrics = ("query_context" in fixed
                      and "query" in fixed.get("query_context", {})
                      and "metrics" in fixed.get("query_context", {}).get("query", {}))

    if viz_type not in NO_METRICS_TYPES and "metrics" in fixed and not has_qc_metrics:
        metrics_list = fixed["metrics"]
        if isinstance(metrics_list, list):
            for i, m in enumerate(metrics_list):
                if isinstance(m, str) and m.strip().lower() != "count":
                    fixed["metrics"][i] = _build_adhoc_metric_from_string(m)

    if viz_type not in NO_METRICS_TYPES and "metrics_b" in fixed:
        metrics_list = fixed["metrics_b"]
        if isinstance(metrics_list, list):
            for i, m in enumerate(metrics_list):
                if isinstance(m, str) and m.strip().lower() != "count":
                    fixed["metrics_b"][i] = _build_adhoc_metric_from_string(m)

    if viz_type not in NO_METRICS_TYPES and has_qc_metrics:
        qc_metrics = fixed["query_context"]["query"]["metrics"]
        if isinstance(qc_metrics, list):
            for i, m in enumerate(qc_metrics):
                if isinstance(m, str) and m.strip().lower() != "count":
                    qc_metrics[i] = _build_adhoc_metric_from_string(m)


def _fix_axis_fields(fixed: Dict[str, Any]) -> None:
    """Convert axis string values to AdHocMetricObject."""
    for axis in ["x", "y", "size", "size_metric", "series"]:
        if axis in fixed and isinstance(fixed[axis], str):
            s = fixed[axis].strip().lower()
            if s == "count":
                continue
            agg, col_name = _parse_string_metric(fixed[axis])
            if agg != "AVG" or col_name != fixed[axis]:
                fixed[axis] = _build_adhoc_metric_from_string(fixed[axis])


def _fix_invalid_column_fields(fixed: Dict[str, Any]) -> None:
    """Strip invalid fields (type, data_type) from metric column objects."""
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


def _fix_metric_labels(fixed: Dict[str, Any]) -> None:
    """Add missing aggregate, expressionType, and label to all metric dicts."""
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


def _fix_groupby_labels(fixed: Dict[str, Any]) -> None:
    """Add missing labels to groupby/orderby/columns dict entries."""
    for field in ["groupby", "orderby", "columns", "all_columns"]:
        if field in fixed and isinstance(fixed[field], list):
            for item in fixed[field]:
                if isinstance(item, dict) and not item.get("label"):
                    col = item.get("column", {}).get("column_name", "")
                    item["label"] = col or "unknown"
