"""
Validation check functions for chart column references.

Contains helper functions that extract and validate column references
from chart parameters against dataset schemas.

Functions:
    _extract_metric_columns: Parse column names from metric expressions
    _extract_columns_from_params: Extract all column references from chart params
    _find_column_suggestions: Find matching columns using fuzzy matching
"""

import logging
import re
from difflib import get_close_matches
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def _extract_metric_columns(metric_str: str) -> List[str]:
    """
    Extract column names from metric expressions.

    Handles formats:
    - "SUM(sales)" -> ["sales"]
    - "AVG(price)" -> ["price"]
    - "COUNT" -> ["count"]
    - "COUNT_DISTINCT(country)" -> ["country"]

    Args:
        metric_str: Metric string to parse

    Returns:
        List of column names extracted from the metric
    """
    columns = []
    metric_lower = metric_str.strip().lower()

    # Handle the special 'count' metric (built-in row count, not a column reference)
    if metric_lower == "count":
        columns.append("count")
        return columns

    # Extract column name from AGGREGATION(column_name) pattern
    match = re.match(
        r"^(SUM|AVG|MIN|MAX|COUNT|COUNT_DISTINCT)\s*\(\s*(.+?)\s*\)$",
        metric_str.strip(),
        re.IGNORECASE,
    )
    if match:
        col = match.group(2).strip()
        if col:
            columns.append(col)

    return columns


def _extract_columns_from_params(
    params: Dict[str, Any],
    actual_viz_type: str,
) -> List[Tuple[str, str]]:
    """
    Extract all column references from chart params.

    Returns list of (field_name, column_value) tuples for all columns
    that need to exist in the dataset.

    Args:
        params: Chart params dict
        actual_viz_type: The actual Superset viz_type

    Returns:
        List of (field_name, column_value) tuples
    """
    column_refs = []

    # Extract from 'metric' (singular) - can be string or AdHocMetricObject dict
    if "metric" in params and params["metric"]:
        metric = params["metric"]
        if isinstance(metric, str):
            for col in _extract_metric_columns(metric):
                column_refs.append(("metric", col))
        elif isinstance(metric, dict):
            col_name = metric.get("column", {}).get("column_name")
            if col_name:
                column_refs.append(("metric (object)", col_name))

    # Extract from 'metrics' (plural array) - list of metric strings/objects
    if "metrics" in params and params["metrics"]:
        metrics = params["metrics"]
        if isinstance(metrics, list):
            for i, metric in enumerate(metrics):
                if isinstance(metric, str):
                    for col in _extract_metric_columns(metric):
                        column_refs.append((f"metrics[{i}]", col))
                elif isinstance(metric, dict):
                    col_name = metric.get("column", {}).get("column_name")
                    if col_name:
                        column_refs.append((f"metrics[{i}] (object)", col_name))

    # Extract from 'groupby' - list of dimension columns for grouping
    if "groupby" in params and params["groupby"]:
        groupby = params["groupby"]
        if isinstance(groupby, list):
            for col in groupby:
                if isinstance(col, str):
                    column_refs.append(("groupby", col))
        elif isinstance(groupby, str):
            column_refs.append(("groupby", groupby))

    # Extract from 'x_axis' (time series x-axis)
    if "x_axis" in params and params["x_axis"]:
        column_refs.append(("x_axis", params["x_axis"]))

    # Extract from scatter/bubble axis fields (x, y, size)
    for axis in ["x", "y", "size"]:
        if axis in params and params[axis]:
            val = params[axis]
            if isinstance(val, str):
                for col in _extract_metric_columns(val):
                    column_refs.append((axis, col))

    # Extract from 'columns' (sunburst, treemap, boxplot, etc.)
    if "columns" in params and params["columns"]:
        cols = params["columns"]
        if isinstance(cols, list):
            for col in cols:
                if isinstance(col, str):
                    column_refs.append(("columns", col))
        elif isinstance(cols, str):
            column_refs.append(("columns", cols))

    # Extract from 'all_columns' (table chart)
    if "all_columns" in params and params["all_columns"]:
        cols = params["all_columns"]
        if isinstance(cols, list):
            for col in cols:
                if isinstance(col, str):
                    column_refs.append(("all_columns", col))

    # Extract from gantt-specific fields (start_time, end_time)
    for field in ["start_time", "end_time"]:
        if field in params and params[field]:
            column_refs.append((field, params[field]))

    # Extract from graph/sankey fields (source, target)
    for field in ["source", "target"]:
        if field in params and params[field]:
            column_refs.append((field, params[field]))

    # Extract from wordcloud/bubble series field
    for field in ["series"]:
        if field in params and params[field]:
            column_refs.append((field, params[field]))

    # Extract from map entity field
    if "entity" in params and params["entity"]:
        column_refs.append(("entity", params["entity"]))

    # Extract from 'orderby' - array of column references with sort direction
    if "orderby" in params and params["orderby"]:
        orderby = params["orderby"]
        if isinstance(orderby, list):
            for i, entry in enumerate(orderby):
                if isinstance(entry, list) and len(entry) >= 1:
                    col = entry[0]
                    if isinstance(col, str) and col.strip():
                        column_refs.append((f"orderby[{i}]", col))
                elif isinstance(entry, dict):
                    col_obj = entry.get("column", {})
                    if isinstance(col_obj, dict):
                        col_name = col_obj.get("column_name")
                        if isinstance(col_name, str) and col_name.strip():
                            column_refs.append((f"orderby[{i}]", col_name))

    # Extract from 'timeseries_limit_metric' - string or AdHocMetricObject
    if "timeseries_limit_metric" in params and params["timeseries_limit_metric"]:
        tlm = params["timeseries_limit_metric"]
        if isinstance(tlm, str):
            for col in _extract_metric_columns(tlm):
                column_refs.append(("timeseries_limit_metric", col))
        elif isinstance(tlm, dict):
            col_name = tlm.get("column", {}).get("column_name")
            if isinstance(col_name, str) and col_name.strip():
                column_refs.append(("timeseries_limit_metric", col_name))

    logger.info(f"Extracted {len(column_refs)} column references from params")
    for field, col in column_refs:
        logger.info(f"  Column ref: {field} -> '{col}'")

    return column_refs


def _find_column_suggestions(
    requested_column: str,
    dataset_columns: List[Dict[str, Any]],
    max_suggestions: int = 3,
) -> List[str]:
    """
    Find suggested column names that might match the requested column.

    Uses case-insensitive matching and fuzzy matching for close typos.

    Args:
        requested_column: The column name requested in chart params
        dataset_columns: List of column dicts from dataset
        max_suggestions: Maximum number of suggestions to return

    Returns:
        List of suggested column names
    """
    requested_lower = requested_column.lower()

    # Case-insensitive exact match - fastest and most reliable check
    for col in dataset_columns:
        col_name = col.get("column_name", "")
        if col_name.lower() == requested_lower:
            logger.info(f"Exact case-insensitive match found: '{requested_column}' -> '{col_name}'")
            return [col_name]

    # Fuzzy matching for typos using difflib's get_close_matches
    available_names = [col.get("column_name", "") for col in dataset_columns]
    suggestions = get_close_matches(
        requested_lower,
        [name.lower() for name in available_names],
        n=max_suggestions,
        cutoff=0.6,
    )

    # Map fuzzy-matched lowercase names back to original case from the dataset
    original_cases = {}
    for name in available_names:
        original_cases[name.lower()] = name

    matched = [original_cases.get(s, s) for s in suggestions]

    if matched:
        logger.info(f"Fuzzy matches for '{requested_column}': {matched}")

    return matched
