"""
Main validation orchestration for chart data against datasets.

Contains the primary validation entry point that ties together column
extraction, temporal checks, and suggestions into a complete validation
result.

Aligned with Superset SQL Developer skill:
- Validates temporal columns (date/time types)
- Validates time_grain_sqla values for time series charts
- Checks that x_axis columns exist and are temporal
- Reports available temporal vs non-temporal columns for LLM guidance
"""

import logging
import re
from typing import Any, Dict, List

from modules.SupersetModule.tools.chart_validation.validator import _is_column_temporal, _get_temporal_columns
from modules.SupersetModule.tools.chart_validation.checks import (
    _extract_columns_from_params,
    _find_column_suggestions,
)

logger = logging.getLogger(__name__)

# Time series chart types that require a temporal x_axis
TIME_SERIES_VIZ_TYPES = {
    "echarts_timeseries_line",
    "echarts_timeseries_bar",
    "echarts_area",
    "echarts_timeseries_scatter",
    "mixed_timeseries",
    "waterfall",
}

# Chart types that need temporal column validation
TEMPORAL_CHART_TYPES = TIME_SERIES_VIZ_TYPES | {
    "big_number",  # when show_trend_line=True
}

# Valid time_grain_sqla values per Superset API
VALID_TIME_GRAINS: set = {
    "P1H", "PT1H",    # Hour
    "P1D", "PT1D",    # Day
    "P1W", "PT1W",    # Week
    "P1M", "PT1M",    # Month
    "P1Y", "PT1Y",    # Year
    "P3M",            # Quarter
    "P6M",            # Half-year
    "daily", "weekly", "monthly", "yearly",  # Legacy string formats
    "hour", "day", "week", "month", "year",  # Alternative formats
}


def _is_valid_iso8601_duration(value: str) -> bool:
    """
    Check if a string is a valid ISO 8601 duration (e.g., P1D, P1M, P1Y, P3M).

    Args:
        value: String to check

    Returns:
        True if the string is a valid ISO 8601 duration pattern
    """
    pattern = (
        r'^P(\d+(?:\.\d+)?Y)?(\d+(?:\.\d+)?M)?(\d+(?:\.\d+)?D)?'
        r'(T(\d+(?:\.\d+)?H)?(\d+(?:\.\d+)?M)?(\d+(?:\.\d+)?S)?)?$'
    )
    return bool(re.match(pattern, value))


def validate_chart_data_against_dataset(
    params: Dict[str, Any],
    dataset_columns: List[Dict[str, Any]],
    actual_viz_type: str,
) -> Dict[str, Any]:
    """
    Validate chart params against actual dataset columns.

    This function runs BEFORE the chart is sent to Superset API to prevent
    "Columns missing in dataset" errors.

    Args:
        params: Chart params dict (after auto_fix and resolve)
        dataset_columns: List of column dicts from dataset API
        actual_viz_type: The actual Superset viz_type (e.g., 'echarts_timeseries_line')

    Returns:
        Dict with validation results:
        - is_valid: True if no blocking errors
        - missing_columns: List of {requested, suggestions, matched}
        - available_columns: List of {name, type, is_temporal}
        - temporal_column_valid: True if temporal columns are OK (for time series)
        - temporal_column_error: Error message if temporal validation failed
        - time_grain_valid: True if time_grain_sqla is valid
        - time_grain_error: Error message if time_grain_sqla is invalid
        - errors: List of error messages
        - warnings: List of warning messages
    """
    logger.info(f"Starting chart data validation for viz_type='{actual_viz_type}'")
    logger.info(f"  Dataset has {len(dataset_columns)} columns")

    # Initialize the result dict with default values
    result: Dict[str, Any] = {
        "is_valid": True,
        "missing_columns": [],
        "available_columns": [],
        "temporal_column_valid": True,
        "temporal_column_error": None,
        "time_grain_valid": True,
        "time_grain_error": None,
        "errors": [],
        "warnings": [],
    }

    # Build case-insensitive lookup of available columns
    available_columns_lower = {}
    for col in dataset_columns:
        col_name = col.get("column_name", "")
        available_columns_lower[col_name.lower()] = col

    # Populate available_columns list with type and temporal info
    for col in dataset_columns:
        col_name = col.get("column_name", "")
        data_type = col.get("data_type", "unknown")
        is_temporal = _is_column_temporal(col, dataset_columns)
        result["available_columns"].append({
            "name": col_name,
            "type": data_type,
            "is_temporal": is_temporal,
        })

    logger.info(f"Built available columns lookup: {list(available_columns_lower.keys())}")

    # Extract all column references from chart params
    column_refs = _extract_columns_from_params(params, actual_viz_type)

    # Validate each column reference against the dataset
    missing_columns = []

    for field_name, column_value in column_refs:
        # Skip 'count' special case (it's a row count, not a column)
        if column_value == "count":
            logger.info(f"Skipping special column 'count' from field '{field_name}'")
            continue

        logger.info(f"Validating column '{column_value}' from field '{field_name}'")

        # Check if column exists (case-insensitive)
        if column_value.lower() in available_columns_lower:
            actual_col = available_columns_lower[column_value.lower()]
            actual_name = actual_col.get("column_name", column_value)
            logger.info(f"  Column '{column_value}' found as '{actual_name}'")
            if column_value != actual_name:
                result["warnings"].append(
                    f"Column '{column_value}' renamed to '{actual_name}' to match dataset"
                )
            continue

        # Column not found - find suggestions
        suggestions = _find_column_suggestions(column_value, dataset_columns)

        missing_entry = {
            "requested": column_value,
            "field": field_name,
            "suggestions": suggestions,
        }
        missing_columns.append(missing_entry)
        result["is_valid"] = False

        if suggestions:
            suggestions_formatted = ", ".join(f"'{s}'" for s in suggestions)
            error_msg = (
                f"Column '{column_value}' not found in dataset. "
                f"Did you mean: {suggestions_formatted}?"
            )
        else:
            error_msg = f"Column '{column_value}' not found in dataset."

        result["errors"].append(error_msg)
        logger.warning(f"  MISSING: {error_msg}")

    result["missing_columns"] = missing_columns
    logger.info(f"Validation found {len(missing_columns)} missing columns")

    # Time-based chart validation
    if actual_viz_type in TIME_SERIES_VIZ_TYPES:
        _validate_time_based_charts(params, actual_viz_type, available_columns_lower, result)

    # Big number with trendline validation
    if actual_viz_type == "big_number":
        _validate_big_number_trendline(params, actual_viz_type, available_columns_lower, result)

    logger.info(
        f"Validation result: is_valid={result['is_valid']}, "
        f"errors={len(result['errors'])}, warnings={len(result['warnings'])}"
    )

    return result


def _validate_time_based_charts(
    params: Dict[str, Any],
    viz_type: str,
    available_columns_lower: Dict[str, Dict[str, Any]],
    result: Dict[str, Any],
) -> None:
    """
    Validate time-based charts for temporal x_axis and time_grain_sqla.

    Per Superset SQL Developer skill, time series charts need:
    1. A temporal x_axis column (date/time type)
    2. A valid time_grain_sqla value (P1D, P1M, P1Y, P3M, etc.)
    """
    # Check x_axis is temporal
    x_axis = params.get("x_axis")
    if x_axis:
        x_axis_lower = x_axis.lower()
        if x_axis_lower in available_columns_lower:
            x_axis_col = available_columns_lower[x_axis_lower]
            is_temporal = _is_column_temporal(x_axis_col, [])

            if not is_temporal:
                result["temporal_column_valid"] = False
                result["temporal_column_error"] = (
                    f"Column '{x_axis}' is not a temporal (date/time) column. "
                    f"Data type: '{x_axis_col.get('data_type', 'unknown')}'. "
                    "Time series charts require a date/time column for x_axis."
                )
                result["is_valid"] = False
                result["errors"].append(
                    f"Temporal validation failed: '{x_axis}' is not a temporal column"
                )
                logger.warning(f"  TEMPORAL ERROR: '{x_axis}' is not temporal")
            else:
                logger.info(f"  Temporal validation PASSED: '{x_axis}' is temporal")

    # Check time_grain_sqla
    time_grain = params.get("time_grain_sqla")
    if time_grain:
        time_grain_str = str(time_grain).strip()

        # Check both as-is and lowercased for case-insensitive matching
        if time_grain_str not in VALID_TIME_GRAINS and time_grain_str.lower() not in VALID_TIME_GRAINS:
            result["time_grain_valid"] = False
            result["time_grain_error"] = (
                f"'time_grain_sqla': '{time_grain}' is not a valid Superset time grain. "
                f"Use ISO 8601 duration format: 'P1D' (day), 'P1M' (month), "
                f"'P1Y' (year), 'P3M' (quarterly), 'P1H' (hour)."
            )
            result["is_valid"] = False
            result["errors"].append(f"Time grain validation failed: invalid time_grain_sqla")
            logger.warning(f"  TIME GRAIN ERROR: '{time_grain}' is invalid")


def _validate_big_number_trendline(
    params: Dict[str, Any],
    viz_type: str,
    available_columns_lower: Dict[str, Dict[str, Any]],
    result: Dict[str, Any],
) -> None:
    """
    Validate big_number chart with trendline for temporal x_axis.

    A big_number chart needs a temporal x_axis only when show_trend_line=True.
    """
    show_trend = params.get("show_trend_line", False)
    if not show_trend:
        return

    x_axis = params.get("x_axis")
    if not x_axis:
        result["temporal_column_valid"] = False
        result["temporal_column_error"] = (
            "Chart type 'big_number' with trendline requires a temporal x_axis column. "
            "Add: 'x_axis': '<temporal_column_name>' (e.g., 'Order_Date')."
        )
        result["is_valid"] = False
        result["errors"].append(
            "Temporal validation failed: Missing temporal x_axis for trendline"
        )
    else:
        x_axis_lower = x_axis.lower()
        if x_axis_lower in available_columns_lower:
            x_axis_col = available_columns_lower[x_axis_lower]
            is_temporal = _is_column_temporal(x_axis_col, [])

            if not is_temporal:
                result["temporal_column_valid"] = False
                result["temporal_column_error"] = (
                    f"Column '{x_axis}' is not a temporal (date/time) column. "
                    f"Data type: '{x_axis_col.get('data_type', 'unknown')}'. "
                    "Big number with trendline requires a date/time column for x_axis."
                )
                result["is_valid"] = False
                result["errors"].append(
                    f"Temporal validation failed: '{x_axis}' is not a temporal column"
                )
