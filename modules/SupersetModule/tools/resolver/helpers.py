"""
Utility functions for metric and column name resolution.

Provides core parsing and matching functions used by the resolver strategies
and orchestrator. These functions handle:
- Metric string parsing (SQL expressions, double-underscore format, bare 'count')
- Case-insensitive column name matching against dataset columns
- Building AdHocMetricObject and AdHocDimensionObject dicts

Usage:
    >>> agg, col = parse_metric_string("SUM(sales)")
    >>> actual = resolve_column_name("sales", dataset_columns)
"""
import re
from typing import Any, Dict, List, Optional, Tuple


def build_adhoc_metric(column_name: str, aggregate: str = "AVG") -> Dict[str, Any]:
    """
    Build an AdHocMetricObject for Superset.

    Creates a properly structured metric object dict that Superset's chart API
    expects. Includes aggregate function, nested column reference, expression type,
    and auto-generated label.

    Args:
        column_name: The database column name to aggregate (e.g. "sales").
        aggregate: Aggregation function. One of: SUM, AVG, MIN, MAX, COUNT, COUNT_DISTINCT.

    Returns:
        Dict formatted as an AdHocMetricObject with keys: aggregate, column, expressionType, label.

        Example:
            >>> build_adhoc_metric("sales", "SUM")
            {'aggregate': 'SUM', 'column': {'column_name': 'sales'}, 'expressionType': 'SIMPLE', 'label': 'SUM(sales)'}
    """
    # Step 1: Build the metric object with required Superset fields:
    #   - aggregate: the aggregation function (SUM, AVG, etc.)
    #   - column: nested dict with column_name for the database column reference
    #   - expressionType: "SIMPLE" for direct column aggregates
    #   - label: auto-generated human-readable label used by the frontend
    return {
        "aggregate": aggregate,
        "column": {"column_name": column_name},
        "expressionType": "SIMPLE",
        "label": f"{aggregate}({column_name})",
    }


def build_adhoc_dimension(column_name: str) -> Dict[str, Any]:
    """
    Build an AdHocDimensionObject for Superset.

    Creates a dimension object dict used for axis values in scatter, bubble,
    and other chart types that accept column references as dimensions.

    Args:
        column_name: The database column name for the dimension.

    Returns:
        Dict formatted as an AdHocDimensionObject with keys: column, expressionType.

        Example:
            >>> build_adhoc_dimension("product_line")
            {'column': {'column_name': 'product_line'}, 'expressionType': 'DIMENSION'}
    """
    # Step 1: Build the dimension object — similar to AdHocMetricObject but
    #   uses expressionType "DIMENSION" (not "SIMPLE") to signal it's a
    #   grouping/dimensional column rather than an aggregated metric.
    return {
        "column": {"column_name": column_name},
        "expressionType": "DIMENSION",
    }


def parse_metric_string(metric_str: str) -> Tuple[str, str]:
    """
    Parse a metric string like 'SUM(sales)' or 'sum__sales' into (aggregate, column_name).

    Extracts the aggregation function and column name from various metric string formats.
    Handles SQL expressions, SQL-style double-underscore format, and bare 'count'.

    Args:
        metric_str: Metric string in one of these formats:
            - SQL expression: 'SUM(sales)', 'AVG(price)', 'COUNT(id)'
            - SQL-style: 'sum__sales', 'avg__count', 'max__value'
            - Simple: 'count' (returns COUNT, "count")

    Returns:
        Tuple of (aggregate, column_name) where aggregate is uppercase (e.g. "SUM", "AVG").

    Example:
        >>> parse_metric_string("SUM(sales)")
        ('SUM', 'sales')
        >>> parse_metric_string("sum__revenue")
        ('SUM', 'revenue')
        >>> parse_metric_string("count")
        ('COUNT', 'count')
    """
    metric_str = metric_str.strip()
    metric_lower = metric_str.lower()

    # Step 1: Handle 'count' as a special case — it's a built-in Superset metric, not a column reference.
    #   Returning ("COUNT", "count") prevents the resolver from trying to find a "count" column.
    if metric_lower == "count":
        return ("COUNT", "count")

    # Step 2: Handle SQL expression format: SUM(column), AVG(column), etc.
    #   The regex captures the aggregate function name and the column inside parentheses,
    #   with tolerance for optional whitespace around the parentheses.
    match = re.match(
        r"^(SUM|AVG|MIN|MAX|COUNT|COUNT_DISTINCT)\s*\(\s*(.+?)\s*\)$",
        metric_str,
        re.IGNORECASE,
    )
    if match:
        return (match.group(1).upper(), match.group(2).strip())

    # Step 3: Handle SQL-style metric names: sum__sales, avg__count, max__value
    #   This double-underscore format is used as a safe alternative when parentheses
    #   are problematic (e.g., in URL encoding or certain API payloads).
    match = re.match(
        r"^(sum|avg|min|max|count|count_distinct)__(.+)$",
        metric_str,
        re.IGNORECASE,
    )
    if match:
        return (match.group(1).upper(), match.group(2))

    # Step 4: Fallback — treat entire string as column name with AVG aggregation.
    #   This handles bare column names like "sales" that are passed without an explicit
    #   aggregate function, defaulting to average.
    return ("AVG", metric_str)


def resolve_column_name(
    requested_column: str,
    dataset_columns: List[Dict[str, Any]],
    case_sensitive: bool = False,
) -> Optional[str]:
    """
    Find the actual column name in the dataset that matches the requested name.

    Performs exact or case-insensitive matching of a requested column name against
    the actual columns available in a Superset dataset. Returns the actual column
    name from the dataset, or None if no match is found.

    Args:
        requested_column: The column name requested in the chart params (e.g. "Sales").
        dataset_columns: List of column dicts from the dataset, each containing a 'column_name' key.
        case_sensitive: If False (default), performs case-insensitive matching. If True, requires exact match.

    Returns:
        The actual column name from the dataset if found, None if not found,
        or requested_column if dataset_columns is empty (no comparison possible).

    Example:
        >>> resolve_column_name("sales", [{"column_name": "Sales"}, {"column_name": "quantity"}])
        'Sales'
        >>> resolve_column_name("Sales", [{"column_name": "sales"}], case_sensitive=True)
        None
    """
    if not dataset_columns:
        return requested_column  # No columns to check against, return original

    if case_sensitive:
        # Step 1: Case-sensitive — find exact match by iterating through all columns.
        #   This is used when column name casing is known to be reliable.
        for col in dataset_columns:
            if col.get("column_name") == requested_column:
                return col.get("column_name")
        return None
    else:
        # Step 2: Case-insensitive — compare lowercased names for lenient matching.
        #   This is the default mode because Superset datasets often have case variations
        #   (e.g., "Sales" in dataset vs "sales" in user-supplied params).
        #   Returns the ORIGINAL casing from the dataset, not the user's casing.
        requested_lower = requested_column.lower()
        for col in dataset_columns:
            if col.get("column_name", "").lower() == requested_lower:
                return col.get("column_name")
        return None
