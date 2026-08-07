"""
Validation formatter for generating LLM-friendly error messages.

Contains functions for formatting validation results into readable
error messages suitable for LLM consumption.

Includes time_grain_sqla error formatting for time series charts.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def format_validation_error(
    validation_result: Dict[str, Any],
    slice_name: str,
    datasource_id: int,
) -> Dict[str, str]:
    """
    Format validation result into LLM-friendly error messages.

    Args:
        validation_result: Output from validate_chart_data_against_dataset
        slice_name: Name of the chart being created
        datasource_id: Dataset ID for context

    Returns:
        Dict with 'title' and 'body' keys containing formatted error message
    """
    logger.info(f"Formatting validation error for chart '{slice_name}'")

    title_parts = []
    body_lines = []

    # Build the error title based on the type of validation failure
    missing_count = len(validation_result.get("missing_columns", []))
    temporal_error = validation_result.get("temporal_column_error")
    time_grain_error = validation_result.get("time_grain_error")

    if time_grain_error:
        title_parts.append("Chart creation blocked: Invalid time_grain_sqla")
    elif temporal_error:
        title_parts.append("Chart creation blocked: Temporal column validation failed")
    elif missing_count > 0:
        title_parts.append("Chart creation blocked: Missing required columns")
    else:
        title_parts.append("Chart creation blocked: Validation failed")

    title = " | ".join(title_parts) if title_parts else "Chart creation blocked"

    body_lines.append(f"")
    body_lines.append(f"Chart '{slice_name}' cannot be created - validation found issues:")
    body_lines.append(f"")

    # Build the time_grain error section
    if time_grain_error:
        body_lines.append(f"Time grain error:")
        body_lines.append(f"  {time_grain_error}")
        body_lines.append(f"  -> Valid time grains: P1D (day), P1M (month), P1Y (year), P3M (quarterly), P1H (hour)")
        body_lines.append(f"")

    # Build the temporal column error section
    if temporal_error:
        body_lines.append(f"Temporal column error:")
        body_lines.append(f"  {temporal_error}")
        body_lines.append(f"")

    # Build the missing columns section with suggestions
    missing_columns = validation_result.get("missing_columns", [])
    if missing_columns:
        body_lines.append(f"Missing columns ({len(missing_columns)}):")
        body_lines.append(f"")

        for i, missing in enumerate(missing_columns, 1):
            requested = missing["requested"]
            field = missing.get("field", "unknown")
            suggestions = missing.get("suggestions", [])

            body_lines.append(f"{i}. '{requested}' (from field '{field}')")

            if suggestions:
                suggestions_str = ", ".join(f"'{s}'" for s in suggestions)
                body_lines.append(f"   -> Did you mean: {suggestions_str}?")
            else:
                body_lines.append(f"   -> No close matches found in dataset")

            body_lines.append(f"")

    # Build the available columns section (grouped by temporal/non-temporal)
    available_columns = validation_result.get("available_columns", [])
    if available_columns:
        body_lines.append(f"Available columns in dataset (ID: {datasource_id}):")
        body_lines.append(f"")

        # Group by type
        temporal_cols = [c for c in available_columns if c.get("is_temporal")]
        non_temporal_cols = [c for c in available_columns if not c.get("is_temporal")]

        if temporal_cols:
            body_lines.append(f"  Temporal columns (date/time):")
            for col in temporal_cols[:10]:
                body_lines.append(f"    - {col['name']} ({col['type']})")
            if len(temporal_cols) > 10:
                body_lines.append(f"    ... and {len(temporal_cols) - 10} more temporal columns")
            body_lines.append(f"")

        if non_temporal_cols:
            body_lines.append(f"  Other columns:")
            for col in non_temporal_cols[:10]:
                body_lines.append(f"    - {col['name']} ({col['type']})")
            if len(non_temporal_cols) > 10:
                body_lines.append(f"    ... and {len(non_temporal_cols) - 10} more columns")
            body_lines.append(f"")

    # Build the warnings section
    warnings = validation_result.get("warnings", [])
    if warnings:
        body_lines.append(f"Warnings ({len(warnings)}):")
        for warning in warnings:
            body_lines.append(f"  - {warning}")
        body_lines.append(f"")

    # Build the action guidance section with fix instructions
    body_lines.append(f"Fix:")
    if missing_columns:
        body_lines.append(f"  Update your chart params to use the correct column names shown above.")
    if temporal_error:
        body_lines.append(f"  Use a temporal (date/time) column for x_axis.")
    if time_grain_error:
        body_lines.append(f"  Use a valid ISO 8601 duration for time_grain_sqla (e.g., P1M, P1Y, P3M).")
    body_lines.append(f"  Then retry chart creation.")

    body = "\n".join(body_lines)

    logger.info(f"Formatted error message: {len(body)} characters")

    return {"title": title, "body": body}
