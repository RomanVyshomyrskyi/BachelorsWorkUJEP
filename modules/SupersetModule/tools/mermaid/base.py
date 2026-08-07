"""
Common Mermaid generation utilities.

Provides shared functions used across chart and dashboard Mermaid diagram
generation: string sanitization, metric name extraction, and groupby extraction.

Usage:
    >>> from modules.SupersetModule.tools.mermaid.base import (
    ...     _sanitize, _extract_metric_name, _extract_groupby
    ... )
"""
from typing import Any, Dict, List


def _extract_metric_name(params: Dict[str, Any]) -> str:
    """Extract a human-readable metric name from chart params for diagram display.

    Tries the singular 'metric' field first, then the first element of the
    'metrics' array. For AdHocMetricObject dicts, formats as 'AGG(col_name)'.
    For strings, returns as-is. Falls back to '?' if no metric found.

    Args:
        params: Chart params dict potentially containing 'metric' or 'metrics'.

    Returns:
        A string like "SUM(sales)", "count", or "?".
    """
    # Step 1: Try singular 'metric' first, then first element of 'metrics' array
    metric = params.get("metric") or (params.get("metrics") or [None])[0]
    # Step 2: If it's an AdHocMetricObject dict, format as aggregate(column_name)
    if isinstance(metric, dict):
        agg = metric.get("aggregate", "?")
        col = metric.get("column", {}).get("column_name", "?")
        return f"{agg}({col})"
    # Step 3: String metrics returned as-is, None becomes '?'
    return str(metric) if metric else "?"


def _extract_groupby(params: Dict[str, Any]) -> List[str]:
    """Extract groupby column names from chart params for diagram axis labels.

    Args:
        params: Chart params dict potentially containing 'groupby' as list.

    Returns:
        List of groupby column name strings, or empty list if not found.
    """
    # Step 1: Get the groupby value — should be a list of column names
    groupby = params.get("groupby", [])
    # Step 2: Ensure it's a list (defensive against string groupby)
    return list(groupby) if isinstance(groupby, list) else []


def _sanitize(val: str) -> str:
    """Sanitize a string for safe embedding in Mermaid diagram syntax.

    Replaces characters that would break Mermaid rendering:
    - Double quotes → single quotes (Mermaid uses double quotes as delimiters)
    - <br/> → space (newline markers don't render in diagram labels)

    Args:
        val: Raw string to sanitize.

    Returns:
        Mermaid-safe string with problematic characters replaced.
    """
    # Step 1: Replace double quotes with single quotes to avoid breaking Mermaid syntax
    # Step 2: Replace HTML <br/> tags with spaces (they have no meaning in diagrams)
    return val.replace('"', "'").replace("<br/>", " ")
