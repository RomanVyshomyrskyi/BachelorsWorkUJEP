"""
Chart parameter validation for Superset charts.

Provides validate_chart_params() which checks chart params against the
expected format for each viz_type. Prevents 'e.column is undefined'
and 'Data error' frontend errors.
"""

import logging
from typing import Any, Dict, List

from .categories import (
    ADHOC_METRICS_ARRAY_TYPES,
    ENTITY_REQUIRED_TYPES,
    MIXED_METRICS_TYPES,
    NO_METRICS_TYPES,
    SANKEY_TYPES,
    SINGULAR_ADHOC_METRIC_TYPES,
    SINGULAR_STRING_METRIC_TYPES,
    STRING_METRICS_ARRAY_TYPES,
)
from .helpers import (
    INVALID_METRIC_STRINGS,
    _is_adhoc_metric_object,
    _is_string_metric,
)

logger = logging.getLogger(__name__)


def validate_chart_params(viz_type: str, params: Dict[str, Any]) -> List[str]:
    """
    Validate chart params and return a list of human-readable error messages.

    Description:
        Performs comprehensive validation of chart parameters against the expected
        format for each viz type. Checks metric format, required fields, axis
        structure, and duplicate labels. Returns an empty list if params are valid.

    Args:
        viz_type: The Superset viz_type string (e.g. "echarts_timeseries_line", "pie").
        params: Chart params dict to validate.

    Returns:
        List of error message strings. Empty list means params are valid.

    Example:
        >>> errors = validate_chart_params("pie", {"groupby": ["product_line"]})
        >>> errors  # Missing 'metric' field
        ["Chart 'pie' is missing 'metric' field. Add: 'metric': 'count' (or 'SUM(column_name)')."]
    """
    errors: List[str] = []
    actual_viz = viz_type

    # Phase 1: Field existence checks (entity, source/target)
    if actual_viz in ENTITY_REQUIRED_TYPES:
        if not params.get("entity"):
            errors.append(
                f"Chart '{actual_viz}' is missing required 'entity' field. "
                f"Add: 'entity': 'country_code' (or the column with country identifiers)."
            )

    if actual_viz in SANKEY_TYPES:
        if "source" not in params:
            errors.append(
                f"Chart '{actual_viz}' is missing required 'source' field. "
                f"Add: 'source': 'channel_1' (the source column name)."
            )
        if "target" not in params:
            errors.append(
                f"Chart '{actual_viz}' is missing required 'target' field. "
                f"Add: 'target': 'channel_2' (the target column name)."
            )

    # Phase 2: Metric format validation per viz type category
    if actual_viz in SINGULAR_STRING_METRIC_TYPES:
        if "metric" not in params and "metrics" not in params:
            errors.append(
                f"Chart '{actual_viz}' is missing 'metric' field. "
                f"Add: 'metric': 'count' (or 'SUM(column_name)')."
            )
        elif "metrics" in params and "metric" not in params:
            errors.append(
                f"Chart '{actual_viz}' uses 'metrics' (plural array) but should use "
                f"'metric' (singular string). Change 'metrics: [...]' to "
                f"'metric: \"count\"'."
            )
        elif "metric" in params:
            metric_val = params["metric"]
            if metric_val is None:
                errors.append(
                    f"Chart '{actual_viz}' has null 'metric'. "
                    f"Set it to 'count' or 'SUM(column_name)'."
                )
            elif _is_string_metric(metric_val):
                ms = metric_val.strip().lower()
                if ms in INVALID_METRIC_STRINGS:
                    errors.append(
                        f"Chart '{actual_viz}' has invalid metric string "
                        f"'{metric_val}'. Use a real metric like 'count' "
                        f"or 'SUM(column_name)'."
                    )
            elif not _is_adhoc_metric_object(metric_val):
                errors.append(
                    f"Chart '{actual_viz}' has invalid 'metric' format. "
                    f"Expected a string (e.g., 'count', 'SUM(column)') or an "
                    f"AdHocMetricObject."
                )

    elif actual_viz in SINGULAR_ADHOC_METRIC_TYPES:
        if "metrics" in params and "metric" not in params:
            errors.append(
                f"Chart '{actual_viz}' uses 'metrics' (plural array) but should use "
                f"'metric' (singular AdHocMetricObject). Change 'metrics: [...]' to "
                f"'metric: {{'aggregate': 'AVG', 'column': {{'column_name': '...'}}, "
                f"'expressionType': 'SIMPLE'}}'."
            )
        elif "metric" in params:
            metric_val = params["metric"]
            if metric_val is None:
                errors.append(
                    f"Chart '{actual_viz}' has null 'metric'. "
                    f"Set it to a valid metric like 'count' or 'SUM(column_name)'."
                )
            elif _is_string_metric(metric_val):
                ms = metric_val.strip().lower()
                if ms in INVALID_METRIC_STRINGS:
                    errors.append(
                        f"Chart '{actual_viz}' has invalid metric string "
                        f"'{metric_val}'. Use a real metric like 'count' "
                        f"or 'SUM(column_name)'."
                    )
            elif isinstance(metric_val, dict) and not _is_adhoc_metric_object(metric_val):
                errors.append(
                    f"Metric object in '{actual_viz}' is missing or has null "
                    f"'column.column_name'. Expected: {{'aggregate': 'AVG', "
                    f"'column': {{'column_name': '...'}}, "
                    f"'expressionType': 'SIMPLE'}}"
                )

    elif actual_viz in STRING_METRICS_ARRAY_TYPES:
        if "metrics" not in params:
            errors.append(
                f"Chart '{actual_viz}' is missing 'metrics' field. "
                f"Add: 'metrics': ['count']."
            )
        elif "metric" in params and "metrics" not in params:
            errors.append(
                f"Chart '{actual_viz}' uses 'metric' (singular) but should use "
                f"'metrics' (array)."
            )
        elif "metrics" in params:
            metrics_list = params["metrics"]
            if isinstance(metrics_list, list):
                for i, m in enumerate(metrics_list):
                    if isinstance(m, dict):
                        if not _is_adhoc_metric_object(m):
                            errors.append(
                                f"Metric {i} in '{actual_viz}' has invalid format. "
                                f"Expected AdHocMetricObject with 'column.column_name'."
                            )
                    elif _is_string_metric(m):
                        ms = m.strip().lower()
                        if ms in INVALID_METRIC_STRINGS:
                            errors.append(
                                f"Metric {i} in '{actual_viz}' has invalid metric string "
                                f"'{m}'. Use a real metric like 'count' or 'SUM(column_name)'."
                            )

    elif actual_viz in ADHOC_METRICS_ARRAY_TYPES:
        if "metrics" not in params:
            errors.append(
                f"Chart '{actual_viz}' is missing 'metrics' field. "
                f"Add: 'metrics': [{{'aggregate': 'SUM', 'column': {{'column_name': '...'}}, "
                f"'expressionType': 'SIMPLE'}}]."
            )
        elif "metric" in params and "metrics" not in params:
            errors.append(
                f"Chart '{actual_viz}' uses 'metric' (singular) but should use "
                f"'metrics' (array of AdHocMetricObjects)."
            )
        elif "metrics" in params:
            metrics_list = params["metrics"]
            if isinstance(metrics_list, list):
                for i, m in enumerate(metrics_list):
                    if _is_string_metric(m):
                        ms = m.strip().lower()
                        if ms in INVALID_METRIC_STRINGS:
                            errors.append(
                                f"Metric {i} in '{actual_viz}' has invalid metric string "
                                f"'{m}'. Use a real metric like 'count' or 'SUM(column_name)'."
                            )
                    elif isinstance(m, dict):
                        if not _is_adhoc_metric_object(m):
                            errors.append(
                                f"Metric {i} in '{actual_viz}' is missing "
                                f"'column.column_name'. Expected: {{'aggregate': 'AVG', "
                                f"'column': {{'column_name': '...'}}, "
                                f"'expressionType': 'SIMPLE'}}"
                            )

    elif actual_viz in MIXED_METRICS_TYPES:
        if "metrics" not in params:
            errors.append(
                f"Chart '{actual_viz}' is missing 'metrics' field. "
                f"Add: 'metrics': ['count']."
            )
        elif "metric" in params and "metrics" not in params:
            errors.append(
                f"Chart '{actual_viz}' uses 'metric' (singular) but should use "
                f"'metrics' (array)."
            )
        elif "metrics" in params:
            metrics_list = params["metrics"]
            if isinstance(metrics_list, list):
                for i, m in enumerate(metrics_list):
                    if _is_string_metric(m):
                        ms = m.strip().lower()
                        if ms in INVALID_METRIC_STRINGS:
                            errors.append(
                                f"Metric {i} in '{actual_viz}' has invalid metric string "
                                f"'{m}'. Use a real metric like 'count' or 'SUM(column_name)'."
                            )
                    elif isinstance(m, dict):
                        if not _is_adhoc_metric_object(m):
                            errors.append(
                                f"Metric {i} in '{actual_viz}' is missing "
                                f"'column.column_name'."
                            )
                    else:
                        errors.append(
                            f"Metric {i} in '{actual_viz}' has invalid type. "
                            f"Expected string or AdHocMetricObject."
                        )

    elif actual_viz in NO_METRICS_TYPES:
        if "metric" in params or "metrics" in params:
            errors.append(
                f"Chart '{actual_viz}' should not have a 'metric' or 'metrics' field."
            )

    # Phase 3: Duplicate label detection
    # Only flag TRUE duplicates - same metric used multiple times with same label.
    # Groupby columns can legitimately share names with metrics (e.g., COUNT(year) grouped by year).
    metric_labels_seen: set = set()
    if "metric" in params:
        m = params["metric"]
        if isinstance(m, str):
            metric_labels_seen.add(m.strip().lower())
        elif isinstance(m, dict):
            label = m.get("label", "") or f"{m.get('aggregate', '')}({m.get('column', {}).get('column_name', '')})"
            if label:
                metric_labels_seen.add(label.lower())

    if "metrics" in params and isinstance(params["metrics"], list):
        for i, m in enumerate(params["metrics"]):
            label = None
            if isinstance(m, str):
                label = m.strip().lower()
            elif isinstance(m, dict):
                label = (m.get("label") or f"{m.get('aggregate', '')}({m.get('column', {}).get('column_name', '')})").lower()
            if label and label in metric_labels_seen:
                errors.append(
                    f"Duplicate metric label '{label}' in metrics[{i}]. "
                    f"All metrics must have unique labels. "
                    f"Use different column names or set explicit 'label' fields."
                )
            elif label:
                metric_labels_seen.add(label)

    # Phase 4: Scatter/bubble axis nesting validation
    if actual_viz in {"scatter", "echarts_timeseries_scatter", "bubble_v2"}:
        for axis in ["x", "y"]:
            if axis in params:
                val = params[axis]
                if isinstance(val, dict):
                    if "column_name" in val and "column" not in val:
                        errors.append(
                            f"'{axis}' in '{actual_viz}' has 'column_name' at top level. "
                            f"Wrap it: '{axis}: {{'column': {{'column_name': '...'}}, "
                            f"'expressionType': 'DIMENSION'}}'."
                        )
                    elif "column" in val and isinstance(val["column"], str):
                        errors.append(
                            f"'{axis}' in '{actual_viz}' has 'column' as a string. "
                            f"Wrap it: '{axis}: {{'column': {{'column_name': '...'}}, "
                            f"'expressionType': 'DIMENSION'}}'."
                        )

    # Phase 5: Required fields for AdHocMetricObjects in singular metric types
    if actual_viz in SINGULAR_ADHOC_METRIC_TYPES and "metric" in params:
        metric_val = params["metric"]
        if isinstance(metric_val, dict) and _is_adhoc_metric_object(metric_val):
            if "aggregate" not in metric_val:
                errors.append(
                    f"Metric in '{actual_viz}' missing 'aggregate' field. "
                    f"Add: 'aggregate': 'AVG' (or SUM, MIN, MAX, COUNT, COUNT_DISTINCT)."
                )
            if "expressionType" not in metric_val:
                errors.append(
                    f"Metric in '{actual_viz}' missing 'expressionType' field. "
                    f"Add: 'expressionType': 'SIMPLE'."
                )

    return errors
