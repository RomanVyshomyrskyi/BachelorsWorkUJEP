"""
Superset metric object builder helpers.

Provides functions to construct correctly formatted AdHocMetricObject
and AdHocDimension dicts for the Superset chart API.

These helpers ensure metrics always have the nested 'column' structure
that Superset's frontend expects, preventing 'e.column is undefined' errors.
"""

from typing import Any, Dict, Optional


# ── Metric Object Builders ───────────────────────────────────────────────────


def build_adhoc_metric(
    column_name: str,
    aggregate: str = "AVG",
    expression_type: str = "SIMPLE",
    label: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a properly formatted AdHocMetricObject dict.

    Args:
        column_name: The database column name (e.g. "SP_DYN_LE00_IN").
        aggregate: Aggregation function. One of: SUM, AVG, MIN, MAX, COUNT, COUNT_DISTINCT.
        expression_type: Expression type. Usually "SIMPLE" or "SQL".
        label: Optional display label (e.g. "AVG(Health Expenditure)").

    Returns:
        A dict formatted as an AdHocMetricObject for the Superset API.

    Example:
        >>> build_adhoc_metric("sales", "SUM")
        {
            "aggregate": "SUM",
            "column": {"column_name": "sales"},
            "expressionType": "SIMPLE",
            "label": "SUM(sales)"
        }
    """
    metric: Dict[str, Any] = {
        "aggregate": aggregate,
        "column": {"column_name": column_name},
        "expressionType": expression_type,
    }
    if label is None:
        label = f"{aggregate}({column_name})"
    metric["label"] = label
    return metric


def build_adhoc_dimension(column_name: str) -> Dict[str, Any]:
    """
    Build a properly formatted AdHocDimension dict for axis values.

    Used by scatter, bubble, and other chart types that use 'x'/'y' axis params.

    Args:
        column_name: The database column name for the axis.

    Returns:
        A dict formatted as an AdHocDimension for the Superset API.

    Example:
        >>> build_adhoc_dimension("SP_DYN_CBRT_IN")
        {
            "column": {"column_name": "SP_DYN_CBRT_IN"},
            "expressionType": "DIMENSION"
        }
    """
    return {
        "column": {"column_name": column_name},
        "expressionType": "DIMENSION",
    }


def build_adhoc_dimension_with_type(
    column_name: str, expression_type: str = "DIMENSION"
) -> Dict[str, Any]:
    """
    Build an AdHocDimension dict with a custom expression type.

    Args:
        column_name: The database column name for the axis.
        expression_type: Either "DIMENSION" or "METRIC".

    Returns:
        A dict formatted as an AdHocDimension.
    """
    return {
        "column": {"column_name": column_name},
        "expressionType": expression_type,
    }


def build_string_metric(metric_str: str) -> str:
    """
    Build a simple string metric for chart types that support it.

    Some chart types (timeseries, heatmap_v2, bubble_v2) accept string metrics
    directly rather than AdHocMetricObject dicts.

    Args:
        metric_str: A string metric like "count", "SUM(sales)", "AVG(price)".

    Returns:
        The string metric unchanged (for compatibility with string-based chart types).

    Example:
        >>> build_string_metric("SUM(sales)")
        "SUM(sales)"
    """
    return metric_str


def parse_string_metric(metric_str: str) -> tuple:
    """
    Parse a string metric into its component parts.

    Args:
        metric_str: A string metric like "SUM(sales)" or "AVG(price)".

    Returns:
        A tuple of (aggregate, column_name).
        Returns ("AVG", metric_str) as fallback if pattern doesn't match.

    Example:
        >>> parse_string_metric("SUM(health_exp)")
        ("SUM", "health_exp")
    """
    import re

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


# ── Quick Metric Factory ─────────────────────────────────────────────────────


def metric(column_name: str, aggregate: str = "AVG") -> Dict[str, Any]:
    """
    Quick factory to build an AdHocMetricObject.

    Short alias for build_adhoc_metric().

    Example:
        >>> metric("sales", "SUM")
        {"aggregate": "SUM", "column": {"column_name": "sales"}, "expressionType": "SIMPLE", "label": "SUM(sales)"}
    """
    return build_adhoc_metric(column_name, aggregate)


def dimension(column_name: str) -> Dict[str, Any]:
    """
    Quick factory to build an AdHocDimension.

    Short alias for build_adhoc_dimension().

    Example:
        >>> dimension("product_line")
        {"column": {"column_name": "product_line"}, "expressionType": "DIMENSION"}
    """
    return build_adhoc_dimension(column_name)
