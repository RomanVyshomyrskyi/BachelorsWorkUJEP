"""
Chart metric validation functions.

Contains _validate_metric_string_format and _validate_metrics_against_dataset.
"""

import os
import json
import re
import logging
from typing import List, Dict, Any, Optional
from modules.SupersetModule.chart_strategies import TYPE_MAP
from modules.SupersetModule.superset_validation import validate_chart_params, NO_METRICS_TYPES
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.exceptions import ChartError
from modules.metrics import get_metrics

from .helpers import (
    CACHE_DIR, CACHE_FILE, CHART_TYPES_CACHE_FILE, CACHE_TTL_SECONDS,
    NUMERIC_TYPES,
)

logger = logging.getLogger(__name__)


def _validate_metric_string_format(params: Dict[str, Any]) -> List[str]:
    """
    Basic syntax validation for metric strings.

    Runs when no dataset schema is available for column-level validation.
    Catches obviously wrong metric strings by parsing their format against
    the expected AGGREGATION(column_name) pattern.

    Args:
        params: Chart params dict containing 'metric', 'metrics', 'entity',
            'orderby', and/or 'timeseries_limit_metric' fields.

    Returns:
        List of error strings. Empty list means all metric strings have
        valid syntax (though not necessarily correct column references).
    """
    errors: List[str] = []

    def check_metric_string(ms: str, label: str) -> None:
        """Validate a single metric string has the expected AGG(col) format.

        Args:
            ms: The metric string to validate (e.g. "SUM(sales)").
            label: Context label for error messages (e.g. "'metric'").

        Returns:
            None — appends error descriptions to the outer ``errors`` list.
        """
        s = ms.strip()
        if not s:
            errors.append(f"Empty metric string in {label}")
            return
        s_lower = s.lower()
        if s_lower == "count":
            return
        match = re.match(r"^(SUM|AVG|MIN|MAX|COUNT|COUNT_DISTINCT)\s*\(\s*.+?\s*\)$", s, re.IGNORECASE)
        if not match:
            errors.append(
                f"'{s}' in {label} has invalid format. "
                f"Expected 'count' or 'AGGREGATION(column_name)' "
                f"(e.g., 'SUM(sales)', 'AVG(price)')."
            )

    if "metric" in params:
        m = params["metric"]
        if m is None:
            errors.append("'metric' is null — set it to 'count' or 'SUM(column_name)'")
        elif isinstance(m, str):
            check_metric_string(m, "'metric'")
        elif isinstance(m, dict):
            col_name = m.get("column", {}).get("column_name")
            if not col_name:
                errors.append("'metric' object has null or missing column_name")

    if "metrics" in params and params["metrics"]:
        for i, m in enumerate(params["metrics"]):
            if isinstance(m, str):
                check_metric_string(m, f"'metrics[{i}]'")
            elif isinstance(m, dict):
                col_name = m.get("column", {}).get("column_name")
                if not col_name:
                    errors.append(f"'metrics[{i}]' object has null or missing column_name")

    if "entity" in params and not params["entity"]:
        errors.append("'entity' is null or empty — set it to a valid column name (e.g., 'country_code')")

    if "orderby" in params and params["orderby"]:
        orderby = params["orderby"]
        if isinstance(orderby, list):
            for i, entry in enumerate(orderby):
                if isinstance(entry, list):
                    if len(entry) >= 1 and entry[0] is None:
                        errors.append(f"'orderby[{i}]' has null column reference")
                elif isinstance(entry, dict):
                    col_entry = entry.get("column", {})
                    col_name = col_entry.get("column_name") if isinstance(col_entry, dict) else None
                    if col_name is None:
                        errors.append(f"'orderby[{i}]' has null or missing column reference")

    if "timeseries_limit_metric" in params:
        tlm = params["timeseries_limit_metric"]
        if tlm is None:
            errors.append("'timeseries_limit_metric' is null — remove it or set to a valid metric")
        elif isinstance(tlm, dict):
            col_name = tlm.get("column", {}).get("column_name")
            if col_name is None:
                errors.append("'timeseries_limit_metric' object has null column_name")

    return errors


def _validate_metrics_against_dataset(
    params: Dict[str, Any],
    dataset_metrics: List[Dict[str, Any]],
    viz_type: str,
    dataset_columns: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    """
    Validate that all metrics used in chart params exist in the dataset.

    When dataset_metrics is empty (common for physical tables), falls back
    to checking that columns referenced in string metrics (e.g., 'SUM(sales)')
    actually exist in dataset_columns and have compatible types.

    Args:
        params: Chart params dict containing metric references.
        dataset_metrics: List of predefined metric dicts from the dataset API.
        viz_type: The chart visualization type (used for context).
        dataset_columns: Optional list of column dicts for fallback validation.

    Returns:
        List of missing/invalid metric descriptions. Empty list = all valid.
    """
    missing_metrics: List[str] = []
    dataset_metric_names = {m["metric_name"] for m in dataset_metrics}

    column_map: Dict[str, Dict[str, Any]] = {}
    if dataset_columns:
        for col in dataset_columns:
            col_name = col.get("column_name", "")
            if col_name:
                column_map[col_name.lower()] = col

    def extract_metric_strings(p: Dict[str, Any]) -> List[str]:
        """Extract all metric strings from chart params."""
        metrics = []
        if "metric" in p and p["metric"]:
            metric_val = p["metric"]
            if isinstance(metric_val, str):
                metrics.append(metric_val)
            elif isinstance(metric_val, dict):
                col_name = metric_val.get("column", {}).get("column_name", "")
                if col_name:
                    agg = metric_val.get("aggregate", "AVG")
                    metrics.append(f"{agg}({col_name})")
        if "metrics" in p and p["metrics"]:
            for m in p["metrics"]:
                if isinstance(m, str):
                    metrics.append(m)
                elif isinstance(m, dict):
                    col_name = m.get("column", {}).get("column_name", "")
                    if col_name:
                        agg = m.get("aggregate", "AVG")
                        metrics.append(f"{agg}({col_name})")
        return metrics

    def parse_metric_string(metric_str: str) -> tuple:
        """Decompose a metric string into (aggregate, column_name)."""
        s = metric_str.strip().lower()
        if s == "count":
            return ("count", "count")
        m = re.match(r"^(sum|avg|min|max|count|count_distinct)\s*\(\s*(.+?)\s*\)$", s)
        if m:
            return (m.group(1), m.group(2).strip())
        return ("", s)

    def normalize_metric(metric_str: str) -> str:
        """Lowercase and strip a metric string for case-insensitive comparison."""
        metric_str = metric_str.strip()
        if metric_str.lower() == "count":
            return "count"
        return metric_str.lower()

    def metric_matches(metric_name: str, target: str) -> bool:
        """Check if a dataset-defined metric matches a target metric string."""
        name_lower = metric_name.lower()
        target_lower = target.lower()
        if name_lower == target_lower:
            return True
        if "__" in name_lower:
            parts = name_lower.split("__", 1)
            agg = parts[0]
            col = parts[1]
            match = re.match(r"^(\w+)\s*\(\s*(.+?)\s*\)$", target)
            if match and match.group(1).lower() == agg and match.group(2).lower() == col:
                return True
        return False

    def column_has_compatible_type(col_name: str, aggregate: str) -> Optional[str]:
        """Verify a column's data type is compatible with an aggregate function."""
        col_info = column_map.get(col_name.lower())
        if not col_info:
            return None
        col_type = str(col_info.get("type", "")).lower()
        if not col_type:
            return None
        if aggregate.lower() not in ("sum", "avg", "min", "max"):
            return None
        if col_name.lower() == "count" and aggregate.lower() in ("count",):
            return None
        is_numeric = any(t in col_type for t in NUMERIC_TYPES)
        if not is_numeric:
            return (
                f"Aggregation '{aggregate}()' on column '{col_info['column_name']}' "
                f"(type: {col_type}) will fail — '{aggregate}()' requires a numeric column. "
                f"Use 'count' for row counts or pick a numeric column."
            )
        return None

    param_metrics = extract_metric_strings(params)

    for pm in param_metrics:
        normalized = normalize_metric(pm)

        if "(" in pm and ")" in pm:
            parse_result = parse_metric_string(pm)
            agg, col_in_metric = parse_result
            if agg in ("count", "count_distinct") and col_in_metric == "count":
                stripped = agg.replace("_distinct", "").replace("_", "").replace("distinct", "")
                missing_metrics.append(
                    f"'{pm}': use '{stripped}' (bare, without parentheses) instead. "
                    f"'{pm}' tries to aggregate a literal column called 'count', "
                    f"not count rows. Replace with '{stripped}'."
                )
                continue
            is_ad_hoc = True
        else:
            is_ad_hoc = False

        parse_result = parse_metric_string(pm)
        agg, col_in_metric = parse_result

        if normalized == "count":
            if dataset_metric_names and not any(m.lower().startswith("count") for m in dataset_metric_names):
                missing_metrics.append(
                    f"'{pm}': 'count' is a built-in metric but no count-like metric was "
                    f"found in the dataset's defined metrics."
                )
            continue

        if dataset_metric_names and not is_ad_hoc:
            found = False
            for dm in dataset_metric_names:
                if metric_matches(dm, pm):
                    found = True
                    break
            if found:
                continue

        if col_in_metric and column_map:
            if col_in_metric in column_map:
                type_error = column_has_compatible_type(col_in_metric, agg)
                if type_error:
                    missing_metrics.append(type_error)
                continue
            else:
                available = [c.get("column_name", "") for c in dataset_columns] if dataset_columns else []
                suggestion = ""
                for avail in available:
                    if avail.lower() == col_in_metric:
                        suggestion = f" Did you mean '{avail}' (case mismatch)?"
                        break
                if not suggestion:
                    from difflib import get_close_matches
                    matches = get_close_matches(col_in_metric, [c.lower() for c in available], n=1, cutoff=0.6)
                    if matches:
                        for avail in available:
                            if avail.lower() == matches[0]:
                                suggestion = f" Did you mean '{avail}'?"
                                break

                missing_metrics.append(
                    f"'{pm}': column '{col_in_metric}' does not exist in this dataset."
                    + suggestion
                    + (f"\nAvailable columns: {', '.join(available[:15])}" if available else "")
                )
                continue

        if not dataset_metric_names and not column_map:
            available = [c.get("column_name", "") for c in dataset_columns] if dataset_columns else []
            missing_metrics.append(
                f"'{pm}' cannot be validated because no dataset schema was retrieved. "
                f"Dataset returned no columns and no predefined metrics. "
                f"Verify the datasource exists and has columns defined."
            )
            continue

        if dataset_metric_names and not is_ad_hoc:
            missing_metrics.append(
                f"'{pm}' does not match any predefined metric in the dataset."
            )

    return missing_metrics
