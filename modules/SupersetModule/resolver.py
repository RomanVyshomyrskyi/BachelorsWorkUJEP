"""
Validate and fix metric column names against actual dataset columns.

Prevents "Metric 'MAX(col)' does not exist" errors by ensuring chart params
use column names that match the dataset's actual columns.
"""

import json
import re
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def build_adhoc_metric(column_name: str, aggregate: str = "AVG") -> Dict[str, Any]:
    """Build an AdHocMetricObject for Superset."""
    return {
        "aggregate": aggregate,
        "column": {"column_name": column_name},
        "expressionType": "SIMPLE",
        "label": f"{aggregate}({column_name})",
    }


def build_adhoc_dimension(column_name: str) -> Dict[str, Any]:
    """Build an AdHocDimensionObject for Superset."""
    return {
        "column": {"column_name": column_name},
        "expressionType": "DIMENSION",
    }


def parse_metric_string(metric_str: str) -> Tuple[str, str]:
    """
    Parse a metric string like 'SUM(sales)' or 'sum__sales' into (aggregate, column_name).
    
    Handles multiple formats:
    - SQL expression: 'SUM(sales)', 'AVG(price)', 'COUNT(id)'
    - SQL-style: 'sum__sales', 'avg__count', 'max__value'
    - Simple: 'count'
    
    Returns (aggregate, column_name) tuple.
    """
    metric_str = metric_str.strip()
    metric_lower = metric_str.lower()
    
    # Handle 'count' as a special case
    if metric_lower == "count":
        return ("COUNT", "count")
    
    # Handle SQL expression format: SUM(column), AVG(column), etc.
    match = re.match(
        r"^(SUM|AVG|MIN|MAX|COUNT|COUNT_DISTINCT)\s*\(\s*(.+?)\s*\)$",
        metric_str,
        re.IGNORECASE,
    )
    if match:
        return (match.group(1).upper(), match.group(2).strip())
    
    # Handle SQL-style metric names: sum__sales, avg__count, max__value
    match = re.match(
        r"^(sum|avg|min|max|count|count_distinct)__(.+)$",
        metric_str,
        re.IGNORECASE,
    )
    if match:
        return (match.group(1).upper(), match.group(2))
    
    # Fallback: treat entire string as column name with AVG aggregation
    return ("AVG", metric_str)


def resolve_column_name(
    requested_column: str,
    dataset_columns: List[Dict[str, Any]],
    case_sensitive: bool = False,
) -> Optional[str]:
    """
    Find the actual column name in the dataset that matches the requested name.
    
    Args:
        requested_column: The column name requested in the chart params.
        dataset_columns: List of column dicts from the dataset (each has 'column_name').
        case_sensitive: If False, do case-insensitive matching.
    
    Returns:
        The actual column name from the dataset, or None if not found.
        Returns requested_column if no columns to check against.
    """
    if not dataset_columns:
        return requested_column  # No columns to check against
    
    if case_sensitive:
        for col in dataset_columns:
            if col.get("column_name") == requested_column:
                return col.get("column_name")
        return None
    else:
        requested_lower = requested_column.lower()
        for col in dataset_columns:
            if col.get("column_name", "").lower() == requested_lower:
                return col.get("column_name")
        return None


def resolve_metrics(
    metrics: Any,
    dataset_columns: List[Dict[str, Any]],
) -> Tuple[Any, List[str]]:
    """
    Resolve metric column names against actual dataset columns.
    
    Args:
        metrics: Either a string metric, a list of string metrics, 
                 an AdHocMetricObject, or a list of AdHocMetricObjects.
        dataset_columns: List of column dicts from the dataset.
    
    Returns:
        Tuple of (resolved_metrics, list_of_warnings).
    """
    warnings = []
    
    if isinstance(metrics, str):
        resolved = _resolve_single_metric(metrics, dataset_columns, warnings)
        return resolved, warnings
    
    if isinstance(metrics, dict):
        # AdHocMetricObject
        if "column" in metrics and isinstance(metrics["column"], dict):
            col_name = metrics["column"].get("column_name", "")
            actual = resolve_column_name(col_name, dataset_columns)
            if actual != col_name:
                metrics["column"]["column_name"] = actual
                warnings.append(f"Metric column '{col_name}' renamed to '{actual}' to match dataset")
            elif actual is None:
                warnings.append(f"Metric column '{col_name}' not found in dataset")
        return metrics, warnings
    
    if isinstance(metrics, list):
        resolved_list = []
        for m in metrics:
            resolved_m, warns = resolve_metrics(m, dataset_columns)
            resolved_list.append(resolved_m)
            warnings.extend(warns)
        return resolved_list, warnings
    
    return metrics, warnings


def _resolve_single_metric(
    metric_str: str,
    dataset_columns: List[Dict[str, Any]],
    warnings: List[str],
) -> str:
    """Resolve a single string metric against dataset columns."""
    # Bare 'count' is a built-in Superset metric, not a column reference.
    # Never convert it to 'COUNT(count)' regardless of dataset columns.
    if metric_str.strip().lower() == "count":
        return metric_str

    agg, col_name = parse_metric_string(metric_str)
    actual = resolve_column_name(col_name, dataset_columns)
    
    if actual is None:
        warnings.append(f"Metric column '{col_name}' not found in dataset")
        return metric_str
    elif actual != col_name:
        warnings.append(f"Metric column '{col_name}' renamed to '{actual}' to match dataset")
        return f"{agg}({actual})"
    elif metric_str != f"{agg}({col_name})":
        # Convert SQL-style names (sum__sales) to proper format (SUM(sales))
        warnings.append(f"Metric '{metric_str}' converted to '{agg}({col_name})' for Superset")
        return f"{agg}({col_name})"
    
    return metric_str


def resolve_groupby(
    groupby: Any,
    dataset_columns: List[Dict[str, Any]],
) -> Tuple[Any, List[str]]:
    """
    Resolve groupby column names against actual dataset columns.
    
    Args:
        groupby: Either a string column name or list of string column names.
        dataset_columns: List of column dicts from the dataset.
    
    Returns:
        Tuple of (resolved_groupby, list_of_warnings).
    """
    warnings = []
    
    if isinstance(groupby, str):
        actual = resolve_column_name(groupby, dataset_columns)
        if actual is None:
            warnings.append(f"Groupby column '{groupby}' not found in dataset")
            return groupby, warnings
        elif actual != groupby:
            warnings.append(f"Groupby column '{groupby}' renamed to '{actual}' to match dataset")
        return actual, warnings
    
    if isinstance(groupby, list):
        resolved_list = []
        for col in groupby:
            resolved_col, warns = resolve_groupby(col, dataset_columns)
            resolved_list.append(resolved_col)
            warnings.extend(warns)
        return resolved_list, warnings
    
    return groupby, warnings


def resolve_chart_params(
    params: Dict[str, Any],
    dataset_columns: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Resolve all metric and groupby column names in chart params.
    
    Args:
        params: Chart params dict (may have 'metric', 'metrics', 'groupby', etc.)
        dataset_columns: List of column dicts from the dataset.
    
    Returns:
        Tuple of (resolved_params, list_of_warnings).
    """
    warnings = []
    resolved = dict(params)
    
    # Resolve 'metric' (singular)
    if "metric" in resolved:
        before = json.dumps(resolved["metric"], default=str)[:300]
        resolved["metric"], warns = resolve_metrics(resolved["metric"], dataset_columns)
        after = json.dumps(resolved["metric"], default=str)[:300]
        if before != after or warns:
            logger.info("Singular metric resolved: before=%s after=%s warnings=%s", before, after, warns)
        warnings.extend(warns)
    
    # Resolve 'metrics' (plural array)
    if "metrics" in resolved:
        before = json.dumps(resolved["metrics"], default=str)[:500]
        resolved["metrics"], warns = resolve_metrics(resolved["metrics"], dataset_columns)
        after = json.dumps(resolved["metrics"], default=str)[:500]
        if before != after or warns:
            logger.info("Metrics resolved: before=%s after=%s warnings=%s", before, after, warns)
        warnings.extend(warns)
    
    # Resolve 'groupby'
    if "groupby" in resolved:
        resolved["groupby"], warns = resolve_groupby(resolved["groupby"], dataset_columns)
        warnings.extend(warns)
    
    # Resolve 'x_axis' for time series charts
    if "x_axis" in resolved and isinstance(resolved["x_axis"], str):
        actual = resolve_column_name(resolved["x_axis"], dataset_columns)
        if actual is None:
            warnings.append(f"X-axis column '{resolved['x_axis']}' not found in dataset")
        elif actual != resolved["x_axis"]:
            warnings.append(f"X-axis column '{resolved['x_axis']}' renamed to '{actual}' to match dataset")
            resolved["x_axis"] = actual
    
    # Resolve axis values for scatter/bubble charts.
    # Only fix column name casing — don't change a plain column reference
    # into an aggregate formula (e.g., 'sales' → 'AVG(sales)').
    # Ad-hoc formulas like 'SUM(sales)' get converted by auto_fix_chart_params.
    for axis in ["x", "y", "size"]:
        if axis in resolved and isinstance(resolved[axis], str):
            if re.match(r"^(SUM|AVG|MIN|MAX|COUNT|COUNT_DISTINCT)\s*\(.+\)$", resolved[axis], re.IGNORECASE):
                # Formula string: resolve column name within it
                agg, col_name = parse_metric_string(resolved[axis])
                actual = resolve_column_name(col_name, dataset_columns)
                if actual is None:
                    warnings.append(f"{axis}-axis metric column '{col_name}' not found in dataset")
                elif actual != col_name:
                    warnings.append(f"{axis}-axis column '{col_name}' renamed to '{actual}'")
                    resolved[axis] = f"{agg}({actual})"
            else:
                # Plain column name: just resolve casing
                actual = resolve_column_name(resolved[axis], dataset_columns)
                if actual is None:
                    warnings.append(f"{axis}-axis column '{resolved[axis]}' not found in dataset")
                elif actual != resolved[axis]:
                    warnings.append(f"{axis}-axis column '{resolved[axis]}' renamed to '{actual}'")
                    resolved[axis] = actual
    
    return resolved, warnings
