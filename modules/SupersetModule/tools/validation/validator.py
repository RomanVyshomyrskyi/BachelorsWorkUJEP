"""
Chart parameter validation for Superset charts.

Provides validate_chart_params() which checks chart params against the
expected format for each viz_type. Prevents 'e.column is undefined'
and 'Data error' frontend errors.

Aligned with Superset Dashboard Designer skill:
- Validates viz_type and datasource format
- Checks chart-specific required fields (entity, columns, series, etc.)
- Validates time_grain_sqla values for time series charts
- Verifies table chart uses query_mode='raw'
"""

import logging
from typing import Any, Dict, List

from .categories import (
    ADHOC_METRICS_ARRAY_TYPES,
    DATASOURCE_REQUIREMENTS,
    ENTITY_REQUIRED_TYPES,
    MIXED_METRICS_TYPES,
    NO_METRICS_TYPES,
    SANKEY_TYPES,
    SINGULAR_ADHOC_METRIC_TYPES,
    SINGULAR_STRING_METRIC_TYPES,
    STRING_METRICS_ARRAY_TYPES,
    TIME_BASED_TYPES,
    VALID_TIME_GRAINS,
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
        format for each viz type. Checks chart structure, metric format, required
        fields, axis structure, time grain, and duplicate labels. Returns an empty
        list if params are valid.

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

    # Phase 0: Basic structure checks (viz_type and datasource)
    _validate_chart_structure(actual_viz, params, errors)

    # Phase 1: Chart-specific required field checks
    _validate_required_fields(actual_viz, params, errors)

    # Phase 2: Metric format validation per viz type category
    _validate_metric_format(actual_viz, params, errors)

    # Phase 3: Duplicate label detection
    _validate_duplicate_labels(actual_viz, params, errors)

    # Phase 4: Scatter/bubble axis nesting validation
    _validate_axis_structure(actual_viz, params, errors)

    # Phase 5: Required fields for AdHocMetricObjects in singular metric types
    _validate_adhoc_metric_fields(actual_viz, params, errors)

    # Phase 6: Time-based chart validation (time_grain_sqla)
    _validate_time_based(actual_viz, params, errors)

    return errors


def _validate_chart_structure(viz_type: str, params: Dict[str, Any], errors: List[str]) -> None:
    """
    Validate basic chart structure fields (viz_type, datasource).

    Superset API requires:
    - 'viz_type': The chart type identifier
    - 'datasource': Format must be '{id}__table' or '{id}__sqla'
    """
    if "viz_type" not in params or not params["viz_type"]:
        errors.append(
            f"Chart is missing 'viz_type' field. "
            f"Add: 'viz_type': '{viz_type}'."
        )

    if "datasource" not in params or not params["datasource"]:
        errors.append(
            f"Chart is missing 'datasource' field. "
            f"Add: 'datasource': '<id>__table' (e.g., '13__table')."
        )


def _validate_required_fields(viz_type: str, params: Dict[str, Any], errors: List[str]) -> None:
    """
    Validate chart-specific required fields from DATASOURCE_REQUIREMENTS.

    Checks fields required by each chart type:
    - world_map: entity
    - bubble_v2: x, y, size
    - sunburst_v2: columns
    - table: query_mode, all_columns
    - tree_chart: id, parent, name
    - word_cloud: series
    - pivot_table_v2: groupbyColumns, groupbyRows
    - sankey_v2: source, target
    - graph_chart: node, relationship
    - gantt_chart: start_time, end_time
    """
    # Phase 1a: Entity field (world_map)
    if viz_type in ENTITY_REQUIRED_TYPES:
        if not params.get("entity"):
            errors.append(
                f"Chart '{viz_type}' is missing required 'entity' field. "
                f"Add: 'entity': 'country_code' (or the column with country identifiers)."
            )

    # Phase 1b: Source/target fields (sankey)
    if viz_type in SANKEY_TYPES:
        if "source" not in params:
            errors.append(
                f"Chart '{viz_type}' is missing required 'source' field. "
                f"Add: 'source': 'channel_1' (the source column name)."
            )
        if "target" not in params:
            errors.append(
                f"Chart '{viz_type}' is missing required 'target' field. "
                f"Add: 'target': 'channel_2' (the target column name)."
            )

    # Phase 1c: Datase-specific required fields from DATASOURCE_REQUIREMENTS
    if viz_type in DATASOURCE_REQUIREMENTS:
        req_config = DATASOURCE_REQUIREMENTS[viz_type]
        required_fields = req_config.get("required", [])

        for field in required_fields:
            if field not in params or not params[field]:
                if field == "columns":
                    errors.append(
                        f"Chart '{viz_type}' is missing required '{field}' field. "
                        f"Add: '{field}': ['year', 'product_line'] (array of hierarchy levels)."
                    )
                elif field in ("query_mode",):
                    errors.append(
                        f"Chart '{viz_type}' is missing required '{field}' field. "
                        f"Add: '{field}': 'raw' (required for table charts)."
                    )
                elif field in ("groupbyColumns", "groupbyRows"):
                    errors.append(
                        f"Chart '{viz_type}' is missing required '{field}' field. "
                        f"Add: '{field}': ['column1', 'column2'] (array of grouping columns)."
                    )
                elif field in ("start_time", "end_time"):
                    errors.append(
                        f"Chart '{viz_type}' is missing required '{field}' field. "
                        f"Add: '{field}': 'order_date' (a temporal column name)."
                    )
                elif field in ("id", "parent", "name"):
                    errors.append(
                        f"Chart '{viz_type}' is missing required '{field}' field. "
                        f"Add: '{field}': 'id' (column name for {field})."
                    )
                elif field == "series":
                    errors.append(
                        f"Chart '{viz_type}' is missing required '{field}' field. "
                        f"Add: '{field}': 'customer_name' (column with text labels)."
                    )
                elif field == "all_columns":
                    errors.append(
                        f"Chart '{viz_type}' is missing required '{field}' field. "
                        f"Add: '{field}': ['col1', 'col2'] (list of columns to display)."
                    )
                elif field == "entity":
                    errors.append(
                        f"Chart '{viz_type}' is missing required '{field}' field. "
                        f"Add: '{field}': 'country_code' (geographic identifier)."
                    )
                elif field in ("x", "y", "size"):
                    errors.append(
                        f"Chart '{viz_type}' is missing required '{field}' field. "
                        f"Add: '{field}': {{'column': {{'column_name': '...'}}, "
                        f"'expressionType': 'DIMENSION'}}."
                    )
                elif field in ("node", "relationship"):
                    errors.append(
                        f"Chart '{viz_type}' is missing required '{field}' field. "
                        f"Add: '{field}': 'node_name' (column name)."
                    )
                else:
                    errors.append(
                        f"Chart '{viz_type}' is missing required '{field}' field."
                    )

    # Phase 1d: Table-specific query_mode check
    if viz_type == "table":
        query_mode = params.get("query_mode")
        if query_mode and query_mode != "raw":
            errors.append(
                f"Chart '{viz_type}' has invalid 'query_mode': '{query_mode}'. "
                f"Use 'query_mode': 'raw' for table charts."
            )
        elif not query_mode:
            errors.append(
                f"Chart '{viz_type}' is missing 'query_mode' field. "
                f"Add: 'query_mode': 'raw'."
            )


def _validate_metric_format(viz_type: str, params: Dict[str, Any], errors: List[str]) -> None:
    """
    Validate metric format per viz type category.

    Checks that metrics use the correct format:
    - SINGULAR_STRING_METRIC_TYPES: metric = "count" or "SUM(column)"
    - SINGULAR_ADHOC_METRIC_TYPES: metric = {"aggregate": "SUM", "column": {...}}
    - STRING_METRICS_ARRAY_TYPES: metrics = ["count", "SUM(col)"]
    - ADHOC_METRICS_ARRAY_TYPES: metrics = [{"aggregate": "SUM", ...}]
    - MIXED_METRICS_TYPES: metrics = ["count", {"aggregate": "AVG", ...}]
    - NO_METRICS_TYPES: no metric/metrics field allowed
    """
    # Category 1: Single string metric
    if viz_type in SINGULAR_STRING_METRIC_TYPES:
        if "metric" not in params and "metrics" not in params:
            errors.append(
                f"Chart '{viz_type}' is missing 'metric' field. "
                f"Add: 'metric': 'count' (or 'SUM(column_name)')."
            )
        elif "metrics" in params and "metric" not in params:
            errors.append(
                f"Chart '{viz_type}' uses 'metrics' (plural array) but should use "
                f"'metric' (singular string). Change 'metrics: [...]' to "
                f"'metric: \"count\"'."
            )
        elif "metric" in params:
            _validate_singular_metric(viz_type, params["metric"], errors)

    # Category 2: Single AdHocMetricObject
    elif viz_type in SINGULAR_ADHOC_METRIC_TYPES:
        if "metrics" in params and "metric" not in params:
            errors.append(
                f"Chart '{viz_type}' uses 'metrics' (plural array) but should use "
                f"'metric' (singular AdHocMetricObject). Change 'metrics: [...]' to "
                f"'metric: {{'aggregate': 'AVG', 'column': {{'column_name': '...'}}, "
                f"'expressionType': 'SIMPLE'}}'."
            )
        elif "metric" in params:
            _validate_singular_metric(viz_type, params["metric"], errors)

    # Category 3: Array of string metrics
    elif viz_type in STRING_METRICS_ARRAY_TYPES:
        if "metrics" not in params:
            errors.append(
                f"Chart '{viz_type}' is missing 'metrics' field. "
                f"Add: 'metrics': ['count']."
            )
        elif "metric" in params and "metrics" not in params:
            errors.append(
                f"Chart '{viz_type}' uses 'metric' (singular) but should use "
                f"'metrics' (array)."
            )
        elif "metrics" in params:
            _validate_metrics_array(viz_type, params["metrics"], errors)

    # Category 4: Array of AdHocMetricObjects
    elif viz_type in ADHOC_METRICS_ARRAY_TYPES:
        if "metrics" not in params:
            errors.append(
                f"Chart '{viz_type}' is missing 'metrics' field. "
                f"Add: 'metrics': [{{'aggregate': 'SUM', 'column': {{'column_name': '...'}}, "
                f"'expressionType': 'SIMPLE'}}]."
            )
        elif "metric" in params and "metrics" not in params:
            errors.append(
                f"Chart '{viz_type}' uses 'metric' (singular) but should use "
                f"'metrics' (array of AdHocMetricObjects)."
            )
        elif "metrics" in params:
            _validate_metrics_array(viz_type, params["metrics"], errors)

    # Category 5: Mixed metrics array
    elif viz_type in MIXED_METRICS_TYPES:
        if "metrics" not in params:
            errors.append(
                f"Chart '{viz_type}' is missing 'metrics' field. "
                f"Add: 'metrics': ['count']."
            )
        elif "metric" in params and "metrics" not in params:
            errors.append(
                f"Chart '{viz_type}' uses 'metric' (singular) but should use "
                f"'metrics' (array)."
            )
        elif "metrics" in params:
            _validate_metrics_array(viz_type, params["metrics"], errors)

    # Category 6: No metrics
    elif viz_type in NO_METRICS_TYPES:
        if "metric" in params or "metrics" in params:
            errors.append(
                f"Chart '{viz_type}' should not have a 'metric' or 'metrics' field."
            )


def _validate_singular_metric(viz_type: str, metric_val: Any, errors: List[str]) -> None:
    """Validate a single metric value (string or AdHocMetricObject)."""
    if metric_val is None:
        errors.append(
            f"Chart '{viz_type}' has null 'metric'. "
            f"Set it to 'count' or 'SUM(column_name)'."
        )
    elif _is_string_metric(metric_val):
        ms = metric_val.strip().lower()
        if ms in INVALID_METRIC_STRINGS:
            errors.append(
                f"Chart '{viz_type}' has invalid metric string "
                f"'{metric_val}'. Use a real metric like 'count' "
                f"or 'SUM(column_name)'."
            )
        elif not _is_adhoc_metric_object(metric_val):
            # String metrics are valid (Superset converts them to AdHocMetricObject)
            pass
    elif isinstance(metric_val, dict):
        if not _is_adhoc_metric_object(metric_val):
            errors.append(
                f"Chart '{viz_type}' has invalid 'metric' format. "
                f"Expected a string (e.g., 'count', 'SUM(column)') or an "
                f"AdHocMetricObject."
            )


def _validate_metrics_array(viz_type: str, metrics_list: Any, errors: List[str]) -> None:
    """Validate a metrics array (string or AdHocMetricObject entries)."""
    if not isinstance(metrics_list, list):
        errors.append(f"Chart '{viz_type}' 'metrics' must be an array.")
        return

    for i, m in enumerate(metrics_list):
        if isinstance(m, dict):
            if not _is_adhoc_metric_object(m):
                errors.append(
                    f"Metric {i} in '{viz_type}' has invalid format. "
                    f"Expected AdHocMetricObject with 'column.column_name'."
                )
        elif _is_string_metric(m):
            ms = m.strip().lower()
            if ms in INVALID_METRIC_STRINGS:
                errors.append(
                    f"Metric {i} in '{viz_type}' has invalid metric string "
                    f"'{m}'. Use a real metric like 'count' or 'SUM(column_name)'."
                )


def _validate_duplicate_labels(viz_type: str, params: Dict[str, Any], errors: List[str]) -> None:
    """
    Detect duplicate metric labels.

    Only flag TRUE duplicates - same metric used multiple times with same label.
    Groupby columns can legitimately share names with metrics
    (e.g., COUNT(year) grouped by year).
    """
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


def _validate_axis_structure(viz_type: str, params: Dict[str, Any], errors: List[str]) -> None:
    """
    Validate scatter/bubble axis nesting structure.

    Bubble and scatter charts require x, y (and size) as AdHocDimensionObject dicts:
    {
        "column": {"column_name": "..."},
        "expressionType": "DIMENSION"
    }
    Not as bare strings or with column_name at top level.
    """
    if viz_type in {"scatter", "echarts_timeseries_scatter", "bubble_v2"}:
        for axis in ["x", "y"]:
            if axis in params:
                val = params[axis]
                if isinstance(val, dict):
                    if "column_name" in val and "column" not in val:
                        errors.append(
                            f"'{axis}' in '{viz_type}' has 'column_name' at top level. "
                            f"Wrap it: '{axis}: {{'column': {{'column_name': '...'}}, "
                            f"'expressionType': 'DIMENSION'}}'."
                        )
                    elif "column" in val and isinstance(val["column"], str):
                        errors.append(
                            f"'{axis}' in '{viz_type}' has 'column' as a string. "
                            f"Wrap it: '{axis}: {{'column': {{'column_name': '...'}}, "
                            f"'expressionType': 'DIMENSION'}}'."
                        )


def _validate_adhoc_metric_fields(viz_type: str, params: Dict[str, Any], errors: List[str]) -> None:
    """
    Validate required fields in AdHocMetricObject dicts.

    For SINGULAR_ADHOC_METRIC_TYPES, ensure the metric object has:
    - aggregate (SUM, AVG, MIN, MAX, COUNT, COUNT_DISTINCT)
    - expressionType (must be 'SIMPLE')
    """
    if viz_type in SINGULAR_ADHOC_METRIC_TYPES and "metric" in params:
        metric_val = params["metric"]
        if isinstance(metric_val, dict) and _is_adhoc_metric_object(metric_val):
            if "aggregate" not in metric_val:
                errors.append(
                    f"Metric in '{viz_type}' missing 'aggregate' field. "
                    f"Add: 'aggregate': 'AVG' (or SUM, MIN, MAX, COUNT, COUNT_DISTINCT)."
                )
            if "expressionType" not in metric_val:
                errors.append(
                    f"Metric in '{viz_type}' missing 'expressionType' field. "
                    f"Add: 'expressionType': 'SIMPLE'."
                )


def _validate_time_based(viz_type: str, params: Dict[str, Any], errors: List[str]) -> None:
    """
    Validate time-based charts for required temporal fields.

    Time-based charts need:
    - time_grain_sqla: Valid ISO 8601 duration (P1D, P1M, P1Y, etc.)
    - x_axis: A temporal (date/time) column when applicable

    Aligned with Superset SQL Developer skill time series patterns.
    """
    if viz_type not in TIME_BASED_TYPES:
        return

    # Check time_grain_sqla
    time_grain = params.get("time_grain_sqla")
    if time_grain:
        time_grain_str = str(time_grain).strip()
        # Check case-insensitively against VALID_TIME_GRAINS
        if time_grain_str not in VALID_TIME_GRAINS and time_grain_str.lower() not in VALID_TIME_GRAINS:
            # Also check if it's a valid ISO 8601 duration pattern
            import re
            if not re.match(r'^P(\d+(?:\.\d+)?Y)?(\d+(?:\.\d+)?M)?(\d+(?:\.\d+)?D)?'
                            r'(T(\d+(?:\.\d+)?H)?(\d+(?:\.\d+)?M)?(\d+(?:\.\d+)?S)?)?$',
                            str(time_grain)):
                errors.append(
                    f"Chart '{viz_type}' has invalid 'time_grain_sqla': '{time_grain}'. "
                    f"Use a valid ISO 8601 duration like 'P1D' (day), 'P1M' (month), "
                    f"'P1Y' (year), or 'P3M' (quarterly)."
                )

    # Check x_axis for temporal charts
    x_axis = params.get("x_axis")
    if viz_type in ("echarts_timeseries_line", "echarts_timeseries_bar",
                    "echarts_area", "echarts_timeseries_scatter",
                    "mixed_timeseries"):
        if not x_axis:
            errors.append(
                f"Chart '{viz_type}' is missing 'x_axis' field. "
                f"Add: 'x_axis': 'order_date' (a temporal/date column)."
            )
