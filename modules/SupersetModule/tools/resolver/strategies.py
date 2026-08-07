"""
Strategy classes for different metric/column resolution approaches.

This module contains strategy classes that encapsulate distinct resolution
logic for various Superset chart field types. Each strategy implements the
same interface (resolve method) returning (resolved_value, warnings) tuples.

Usage:
    strategies = [
        MetricStrategy(dataset_columns),
        GroupbyStrategy(dataset_columns),
        AxisStrategy(dataset_columns),
    ]
"""
import re
from typing import Any, Dict, List, Tuple

from modules.SupersetModule.tools.resolver.helpers import (
    parse_metric_string,
    resolve_column_name,
)


class MetricStrategy:
    """
    Strategy for resolving metric column names against dataset columns.

    Handles string metrics ("SUM(sales)"), AdHocMetricObject dicts, and
    lists of metrics. Collects warnings for renamed or missing columns.

    Args:
        dataset_columns: List of column dicts from the dataset for reference.
    """

    def __init__(self, dataset_columns: List[Dict[str, Any]]) -> None:
        self.dataset_columns = dataset_columns

    def resolve(self, metrics: Any) -> Tuple[Any, List[str]]:
        """
        Resolve a metric in any supported format.

        Args:
            metrics: Can be str, dict (AdHocMetricObject), or list.

        Returns:
            Tuple of (resolved_metrics, list_of_warnings).
        """
        warnings = []

        if isinstance(metrics, str):
            resolved = self._resolve_single(metrics, warnings)
            return resolved, warnings

        if isinstance(metrics, dict):
            return self._resolve_adhoc_metric(metrics, warnings)

        if isinstance(metrics, list):
            return self._resolve_list(metrics, warnings)

        return metrics, warnings

    def _resolve_single(self, metric_str: str, warnings: List[str]) -> str:
        """Resolve a single string metric like 'SUM(sales)'."""
        if metric_str.strip().lower() == "count":
            return metric_str

        agg, col_name = parse_metric_string(metric_str)
        actual = resolve_column_name(col_name, self.dataset_columns)

        if actual is None:
            warnings.append(f"Metric column '{col_name}' not found in dataset")
            return metric_str
        elif actual != col_name:
            warnings.append(f"Metric column '{col_name}' renamed to '{actual}' to match dataset")
            return f"{agg}({actual})"
        elif metric_str != f"{agg}({col_name})":
            warnings.append(f"Metric '{metric_str}' converted to '{agg}({col_name})' for Superset")
            return f"{agg}({col_name})"

        return metric_str

    def _resolve_adhoc_metric(self, metrics: Dict[str, Any], warnings: List[str]) -> Tuple[Dict[str, Any], List[str]]:
        """Resolve the nested column_name inside an AdHocMetricObject dict."""
        if "column" in metrics and isinstance(metrics["column"], dict):
            col_name = metrics["column"].get("column_name", "")
            actual = resolve_column_name(col_name, self.dataset_columns)
            if actual != col_name:
                metrics["column"]["column_name"] = actual
                warnings.append(f"Metric column '{col_name}' renamed to '{actual}' to match dataset")
            elif actual is None:
                warnings.append(f"Metric column '{col_name}' not found in dataset")
        return metrics, warnings

    def _resolve_list(self, metrics: List[Any], warnings: List[str]) -> Tuple[List[Any], List[str]]:
        """Recursively resolve each element in a metrics list."""
        resolved_list = []
        for m in metrics:
            resolved_m, warns = self.resolve(m)
            resolved_list.append(resolved_m)
            warnings.extend(warns)
        return resolved_list, warnings


class GroupbyStrategy:
    """
    Strategy for resolving groupby column names against dataset columns.

    Handles single string groupby values and lists of groupby columns.

    Args:
        dataset_columns: List of column dicts from the dataset for reference.
    """

    def __init__(self, dataset_columns: List[Dict[str, Any]]) -> None:
        self.dataset_columns = dataset_columns

    def resolve(self, groupby: Any) -> Tuple[Any, List[str]]:
        """
        Resolve groupby column name(s).

        Args:
            groupby: Either a single column name string or list of strings.

        Returns:
            Tuple of (resolved_groupby, list_of_warnings).
        """
        warnings = []

        if isinstance(groupby, str):
            actual = resolve_column_name(groupby, self.dataset_columns)
            if actual is None:
                warnings.append(f"Groupby column '{groupby}' not found in dataset")
                return groupby, warnings
            elif actual != groupby:
                warnings.append(f"Groupby column '{groupby}' renamed to '{actual}' to match dataset")
            return actual, warnings

        if isinstance(groupby, list):
            resolved_list = []
            for col in groupby:
                resolved_col, warns = self.resolve(col)
                resolved_list.append(resolved_col)
                warnings.extend(warns)
            return resolved_list, warnings

        return groupby, warnings


class AxisStrategy:
    """
    Strategy for resolving axis values for scatter/bubble charts.

    Handles both formula strings (e.g. "SUM(sales)") and plain column names.

    Args:
        dataset_columns: List of column dicts from the dataset for reference.
    """

    def __init__(self, dataset_columns: List[Dict[str, Any]]) -> None:
        self.dataset_columns = dataset_columns
        self._formula_pattern = r"^(SUM|AVG|MIN|MAX|COUNT|COUNT_DISTINCT)\s*\(.+\)$"

    def resolve(self, axis_name: str, value: str) -> Tuple[str, List[str]]:
        """
        Resolve a single axis value.

        Args:
            axis_name: The axis field name (e.g. "x", "y", "size").
            value: The axis value string to resolve.

        Returns:
            Tuple of (resolved_value, list_of_warnings).
        """
        warnings = []

        if re.match(self._formula_pattern, value, re.IGNORECASE):
            agg, col_name = parse_metric_string(value)
            actual = resolve_column_name(col_name, self.dataset_columns)
            if actual is None:
                warnings.append(f"{axis_name}-axis metric column '{col_name}' not found in dataset")
            elif actual != col_name:
                warnings.append(f"{axis_name}-axis column '{col_name}' renamed to '{actual}'")
                return f"{agg}({actual})", warnings
        else:
            actual = resolve_column_name(value, self.dataset_columns)
            if actual is None:
                warnings.append(f"{axis_name}-axis column '{value}' not found in dataset")
            elif actual != value:
                warnings.append(f"{axis_name}-axis column '{value}' renamed to '{actual}'")
                return actual, warnings

        return value, warnings
