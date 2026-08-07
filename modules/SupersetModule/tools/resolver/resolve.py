"""
Main resolve_chart_params() function and orchestrator logic.

This module provides the central entry point for the column resolution pipeline.
The resolver processes all metric-related fields in chart params and corrects
column names to match the dataset's actual columns.

Column Name Resolution Pipeline:
    1. **Metric parsing** (`parse_metric_string`): Extracts aggregate function and
       column name from strings like 'SUM(sales)', 'sum__revenue', or bare 'count'.
    2. **Column lookup** (`resolve_column_name`): Performs case-insensitive matching
       of requested column names against the dataset's actual columns.
    3. **Metric resolution** (`resolve_metrics`): Recursively processes string metrics,
       AdHocMetricObject dicts, or lists of metrics, correcting column names.
    4. **Groupby resolution** (`resolve_groupby`): Corrects column case in groupby
       fields (string or list).
    5. **Orchestrator** (`resolve_chart_params`): The main entry point that dispatches
       all metric-related fields through the resolver pipeline and collects warnings.

    The pipeline is additive-only — invalid columns are warned about but never removed,
    preserving the caller's original intent while correcting what can be fixed.

Usage:
    resolved_params, warnings = resolve_chart_params(params, dataset_columns)
"""
import json
import logging
from typing import Any, Dict, List, Tuple

from modules.SupersetModule.tools.resolver.helpers import resolve_column_name
from modules.SupersetModule.tools.resolver.strategies import (
    AxisStrategy,
    GroupbyStrategy,
    MetricStrategy,
)

logger = logging.getLogger(__name__)


def resolve_metrics(
    metrics: Any,
    dataset_columns: List[Dict[str, Any]],
) -> Tuple[Any, List[str]]:
    """
    Resolve metric column names against actual dataset columns.

    Recursively processes metrics in various formats (string, dict, list) and
    corrects column names to match the dataset's actual column names.
    Collects warnings for any columns that were renamed or not found.

    Args:
        metrics: Metric to resolve. Can be:
            - str: A metric string like "SUM(sales)"
            - dict: An AdHocMetricObject with nested column structure
            - list: A list of any of the above
        dataset_columns: List of column dicts from the dataset for reference.

    Returns:
        Tuple of (resolved_metrics, list_of_warnings) where:
            - resolved_metrics: The metrics with corrected column names
            - list_of_warnings: Human-readable warnings about changes made

    Example:
        >>> resolve_metrics("SUM(sales)", [{"column_name": "Sales"}])
        ('SUM(Sales)', ["Metric column 'sales' renamed to 'Sales' to match dataset"])
    """
    strategy = MetricStrategy(dataset_columns)
    return strategy.resolve(metrics)


def resolve_groupby(
    groupby: Any,
    dataset_columns: List[Dict[str, Any]],
) -> Tuple[Any, List[str]]:
    """
    Resolve groupby column names against actual dataset columns.

    Recursively processes groupby column names (string or list) and corrects
    them to match the dataset's actual column names. Collects warnings for
    renamed or missing columns.

    Args:
        groupby: Groupby value — either a single column name string or list of strings.
        dataset_columns: List of column dicts from the dataset for reference.

    Returns:
        Tuple of (resolved_groupby, list_of_warnings).

    Example:
        >>> resolve_groupby("product_line", [{"column_name": "Product_Line"}])
        ('Product_Line', ["Groupby column 'product_line' renamed to 'Product_Line' to match dataset"])
    """
    strategy = GroupbyStrategy(dataset_columns)
    return strategy.resolve(groupby)


def resolve_chart_params(
    params: Dict[str, Any],
    dataset_columns: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Resolve all metric and groupby column names in chart params.

    Master resolver that processes all metric-related fields in a chart params dict:
    'metric' (singular), 'metrics' (plural array), 'groupby', 'x_axis', and
    scatter/bubble axis fields (x, y, size, size_metric, series).
    Corrects all column names to match the dataset and collects warnings.

    Args:
        params: Chart params dict that may contain any of the following keys:
            'metric', 'metrics', 'groupby', 'x_axis', 'x', 'y', 'size', 'size_metric', 'series'.
        dataset_columns: List of column dicts from the dataset for reference.

    Returns:
        Tuple of (resolved_params, list_of_warnings) where:
            - resolved_params: A copy of params with all column names corrected
            - list_of_warnings: Human-readable warnings about all changes made

    Example:
        >>> params = {"metric": "SUM(sales)", "groupby": "product_line"}
        >>> resolved, warns = resolve_chart_params(params, [{"column_name": "Sales"}])
        >>> resolved["metric"]
        'SUM(Sales)'
    """
    warnings = []
    resolved = dict(params)  # Shallow copy to avoid mutating the original

    # ── Phase 1: Resolve 'metric' (singular) ──
    if "metric" in resolved:
        before = json.dumps(resolved["metric"], default=str)[:300]
        resolved["metric"], warns = resolve_metrics(resolved["metric"], dataset_columns)
        after = json.dumps(resolved["metric"], default=str)[:300]
        if before != after or warns:
            logger.info("Singular metric resolved: before=%s after=%s warnings=%s", before, after, warns)
        warnings.extend(warns)

    # ── Phase 2: Resolve 'metrics' (plural array) ──
    if "metrics" in resolved:
        before = json.dumps(resolved["metrics"], default=str)[:500]
        resolved["metrics"], warns = resolve_metrics(resolved["metrics"], dataset_columns)
        after = json.dumps(resolved["metrics"], default=str)[:500]
        if before != after or warns:
            logger.info("Metrics resolved: before=%s after=%s warnings=%s", before, after, warns)
        warnings.extend(warns)

    # ── Phase 3: Resolve 'groupby' ──
    if "groupby" in resolved:
        resolved["groupby"], warns = resolve_groupby(resolved["groupby"], dataset_columns)
        warnings.extend(warns)

    # ── Phase 4: Resolve 'x_axis' for time series charts ──
    if "x_axis" in resolved and isinstance(resolved["x_axis"], str):
        actual = resolve_column_name(resolved["x_axis"], dataset_columns)
        if actual is None:
            warnings.append(f"X-axis column '{resolved['x_axis']}' not found in dataset")
        elif actual != resolved["x_axis"]:
            warnings.append(f"X-axis column '{resolved['x_axis']}' renamed to '{actual}' to match dataset")
            resolved["x_axis"] = actual

    # ── Phase 5: Resolve axis values for scatter/bubble charts ──
    axis_strategy = AxisStrategy(dataset_columns)
    for axis in ["x", "y", "size", "size_metric", "series"]:
        if axis in resolved and isinstance(resolved[axis], str):
            resolved[axis], warns = axis_strategy.resolve(axis, resolved[axis])
            warnings.extend(warns)

    return resolved, warnings
