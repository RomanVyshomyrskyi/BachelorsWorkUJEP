"""
Helper functions for metric detection and conversion.

Provides utilities to identify AdHocMetricObject dicts, string metrics,
and convert between formats. Used by validate_chart_params and
auto_fix_chart_params.
"""

import re
from typing import Any, Dict, Tuple

INVALID_METRIC_STRINGS: set = {
    "undefined", "null", "none", "",
}


def _is_adhoc_metric_object(val: Any) -> bool:
    """
    Check if a value is a properly formatted AdHocMetricObject dict.
        Validates that a dict has the required nested structure of an AdHocMetricObject:
        a 'column' key containing a dict with a non-empty 'column_name' string.

    Args:
        val: Value to check.

    Returns:
        True if val is a dict with valid column.column_name structure, False otherwise.
    """
    if not isinstance(val, dict):
        return False
    column = val.get("column")
    if not isinstance(column, dict):
        return False
    column_name = column.get("column_name")
    return bool(column_name and isinstance(column_name, str))


def _is_string_metric(val: Any) -> bool:
    """
    Check if a value is a valid string metric like 'count', 'SUM(col)', etc.
        Returns True if val is a non-empty, non-whitespace string that could
        represent a metric (e.g. "count", "SUM(sales)", "AVG(price)").

    Args:
        val: Value to check.

    Returns:
        True if val is a non-empty string, False otherwise.
    """
    if not isinstance(val, str):
        return False
    return val.strip() != ""


def _parse_string_metric(metric_str: str) -> Tuple[str, str]:
    """
    Parse a string metric like 'SUM(sales)' or 'AVG(price)' into (aggregate, column_name).
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
    """
    Convert a string metric like 'SUM(sales)' to an AdHocMetricObject.
        Parses a string metric and constructs a properly nested AdHocMetricObject
        dict with aggregate, column, expressionType, and label fields.
        Handles both 'SUM(sales)' and 'sum__SP_POP_TOTL' (Superset internal) formats.

    Args:
        metric_str: String metric like 'SUM(sales)', 'AVG(price)', or 'sum__sales'.

    Returns:
        Dict formatted as an AdHocMetricObject with all required fields.

    Examples:
        >>> _build_adhoc_metric_from_string("SUM(sales)")
        {'aggregate': 'SUM', 'column': {'column_name': 'sales'}, 'expressionType': 'SIMPLE', 'label': 'SUM(sales)'}
    """
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

    agg, col_name = _parse_string_metric(metric_str)

    return {
        "aggregate": agg,
        "column": {"column_name": col_name},
        "expressionType": "SIMPLE",
        "label": f"{agg}({col_name})",
    }
