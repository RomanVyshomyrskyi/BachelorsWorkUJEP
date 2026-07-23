"""
Superset metric object builder helpers.

Provides functions to construct correctly formatted AdHocMetricObject
and AdHocDimension dicts for the Superset chart API.

Architecture Overview:
    This module offers two tiers of builders:

    Tier 1 — Full Builders (detailed control):
        - `build_adhoc_metric()`: Constructs an AdHocMetricObject with explicit control
          over column_name, aggregate function, expressionType, and label.
        - `build_adhoc_dimension()`: Constructs an AdHocDimension for axis values.
        - `build_adhoc_dimension_with_type()`: Same as above but with custom expression type.
        - `parse_string_metric()`: Decomposes a string metric into (aggregate, column) tuple.

    Tier 2 — Quick Factories (convenience aliases):
        - `metric()`: Short alias for `build_adhoc_metric()` — create a metric in one call.
        - `dimension()`: Short alias for `build_adhoc_dimension()` — create a dimension quickly.

    All builders ensure metrics always have the nested 'column' structure
    that Superset's frontend expects, preventing 'e.column is undefined' errors.
    The nested structure is: {"aggregate": "...", "column": {"column_name": "..."}, ...}
    which is required by Superset 6.x for ALL chart types.
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
    # Step 1: Build the base metric object with required fields.
    #   'aggregate': which aggregation function to apply (SUM, AVG, etc.)
    #   'column': must be a nested dict with 'column_name' — NOT a flat string
    #   'expressionType': "SIMPLE" for direct column references, "SQL" for custom expressions
    metric: Dict[str, Any] = {
        "aggregate": aggregate,
        "column": {"column_name": column_name},
        "expressionType": expression_type,
    }
    # Step 2: Assign label — use the provided label or auto-generate from aggregate + column.
    #   The label is used in chart legends, tooltips, and the metrics selector.
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
    # Step 1: Build the dimension dict — structure mirrors AdHocMetricObject but
    #   expressionType is "DIMENSION" (not "SIMPLE"), telling Superset this is
    #   a grouping/categorization column rather than an aggregated value.
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
    # Step 1: Build dimension with the specified expression type.
    #   "DIMENSION" is used for grouping/axis references,
    #   "METRIC" is used when the dimension itself is an aggregate value.
    return {
        "column": {"column_name": column_name},
        "expressionType": expression_type,
    }


def build_string_metric(metric_str: str) -> str:
    """
    Build a simple string metric for chart types that support it.

    Description:
        Some chart types (timeseries, heatmap_v2, bubble_v2) accept string metrics
        directly rather than AdHocMetricObject dicts. This function is a
        pass-through that preserves the string format for those chart types.

    Args:
        metric_str: A string metric like "count", "SUM(sales)", "AVG(price)".

    Returns:
        The string metric unchanged (for compatibility with string-based chart types).

    Example:
        >>> build_string_metric("SUM(sales)")
        "SUM(sales)"
    """
    # Step 1: Return the string unchanged — this is a compatibility wrapper
    #   that exists so callers can use a consistent interface regardless of
    #   whether the target chart type uses string or object metrics.
    return metric_str


def parse_string_metric(metric_str: str) -> tuple:
    """
    Parse a string metric into its component parts.

    Description:
        Decomposes a metric string like "SUM(sales)" into the aggregate function
        and the column name. Used when converting string metrics to AdHocMetricObject
        format or when extracting column references for resolution.

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
    # Step 1: Special case — bare 'count' is a built-in metric (COUNT(*))
    if metric_str.lower() == "count":
        return ("COUNT", "count")

    # Step 2: Match SQL expression format with case-insensitive regex
    match = re.match(
        r"^(SUM|AVG|MIN|MAX|COUNT|COUNT_DISTINCT)\s*\(\s*(.+?)\s*\)$",
        metric_str,
        re.IGNORECASE,
    )
    if match:
        return (match.group(1).upper(), match.group(2).strip())

    # Step 3: Fallback — treat entire string as column name with AVG aggregation
    return ("AVG", metric_str)


# ── Quick Metric Factory ─────────────────────────────────────────────────────


def metric(column_name: str, aggregate: str = "AVG") -> Dict[str, Any]:
    """
    Quick factory to build an AdHocMetricObject.

    Short alias for build_adhoc_metric(). Designed for rapid chart construction
    where you want a metric object without the full parameter list.

    Example:
        >>> metric("sales", "SUM")
        {"aggregate": "SUM", "column": {"column_name": "sales"}, "expressionType": "SIMPLE", "label": "SUM(sales)"}
    """
    # Step 1: Delegate to the full builder with default expressionType and label
    return build_adhoc_metric(column_name, aggregate)


def dimension(column_name: str) -> Dict[str, Any]:
    """
    Quick factory to build an AdHocDimension.

    Short alias for build_adhoc_dimension(). Designed for rapid chart construction
    where you need a dimension object for axis values.

    Example:
        >>> dimension("product_line")
        {"column": {"column_name": "product_line"}, "expressionType": "DIMENSION"}
    """
    # Step 1: Delegate to the full dimension builder
    return build_adhoc_dimension(column_name)
