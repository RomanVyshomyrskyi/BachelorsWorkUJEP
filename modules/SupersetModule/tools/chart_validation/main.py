"""
Main validation orchestration for chart data against datasets.

Contains the primary validation entry point that ties together column
extraction, temporal checks, and suggestions into a complete validation
result.

Functions:
    validate_chart_data_against_dataset: Main validation entry point
"""

import logging
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

    # Temporal column validation for time series charts
    if actual_viz_type in TEMPORAL_CHART_TYPES:
        logger.info(f"Temporal validation required for viz_type='{actual_viz_type}'")

        # Get x_axis column value
        x_axis = params.get("x_axis")
        if not x_axis:
            # Check if there's a temporal column in the params at all
            if actual_viz_type == "big_number":
                show_trend = params.get("show_trend_line", False)
                if show_trend:
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
                result["temporal_column_valid"] = False
                result["temporal_column_error"] = (
                    f"Chart type '{actual_viz_type}' requires a temporal x_axis column. "
                    "Add: 'x_axis': '<temporal_column_name>' (must be a date/time column)."
                )
                result["is_valid"] = False
                result["errors"].append(
                    "Temporal validation failed: Missing x_axis column"
                )
        else:
            # Check if x_axis column is temporal
            x_axis_lower = x_axis.lower()
            if x_axis_lower in available_columns_lower:
                x_axis_col = available_columns_lower[x_axis_lower]
                is_temporal = _is_column_temporal(x_axis_col, dataset_columns)

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
            else:
                # x_axis column not found - already reported in missing_columns
                pass

    logger.info(
        f"Validation result: is_valid={result['is_valid']}, "
        f"errors={len(result['errors'])}, warnings={len(result['warnings'])}"
    )

    return result
