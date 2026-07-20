"""
Pre-chart data validation against actual dataset columns.

Prevents "Columns missing in dataset" errors by validating all column
references BEFORE the chart is sent to Superset API.

Provides structured validation results with:
- Missing columns with suggestions
- Temporal column validation for time series charts
- LLM-friendly error messages
"""

import logging
import re
import time
from difflib import get_close_matches
from typing import Any, Dict, List, Optional, Set, Tuple

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


def _is_column_temporal(column: Dict[str, Any], dataset_columns: List[Dict[str, Any]]) -> bool:
    """
    Check if a column is temporal (date/time) based on dataset metadata.
    
    Args:
        column: Column dict from dataset (has 'column_name', 'data_type', etc.)
        dataset_columns: Full list of dataset columns
    
    Returns:
        True if the column is temporal (datetime, date, timestamp, etc.)
    """
    col_name = column.get("column_name", "")
    data_type = column.get("data_type", "").lower()
    is_dttm = column.get("is_dttm", False)
    
    logger.info(f"Checking if column '{col_name}' is temporal: data_type={data_type}, is_dttm={is_dttm}")
    
    # Explicit is_dttm flag
    if is_dttm:
        logger.info(f"Column '{col_name}' marked as temporal (is_dttm=True)")
        return True
    
    # Check data type keywords
    temporal_keywords = [
        "date", "time", "timestamp", "datetime", "timetz",
        "timestamptz", "interval", "year",
    ]
    
    for keyword in temporal_keywords:
        if keyword in data_type:
            logger.info(f"Column '{col_name}' identified as temporal by data_type='{data_type}'")
            return True
    
    logger.info(f"Column '{col_name}' is NOT temporal")
    return False


def _get_temporal_columns(dataset_columns: List[Dict[str, Any]]) -> List[str]:
    """
    Extract list of temporal column names from dataset.
    
    Args:
        dataset_columns: List of column dicts from dataset
    
    Returns:
        List of column names that are temporal
    """
    temporal_cols = []
    for col in dataset_columns:
        if _is_column_temporal(col, dataset_columns):
            temporal_cols.append(col["column_name"])
    
    logger.info(f"Found {len(temporal_cols)} temporal columns: {temporal_cols}")
    return temporal_cols


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
    
    if metric_lower == "count":
        columns.append("count")
        return columns
    
    # Extract column from aggregation functions
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
    
    # Extract from 'metric' (singular)
    if "metric" in params and params["metric"]:
        metric = params["metric"]
        if isinstance(metric, str):
            for col in _extract_metric_columns(metric):
                column_refs.append(("metric", col))
        elif isinstance(metric, dict):
            col_name = metric.get("column", {}).get("column_name")
            if col_name:
                column_refs.append(("metric (object)", col_name))
    
    # Extract from 'metrics' (plural array)
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
    
    # Extract from 'groupby'
    if "groupby" in params and params["groupby"]:
        groupby = params["groupby"]
        if isinstance(groupby, list):
            for col in groupby:
                if isinstance(col, str):
                    column_refs.append(("groupby", col))
        elif isinstance(groupby, str):
            column_refs.append(("groupby", groupby))
    
    # Extract from 'x_axis' (time series)
    if "x_axis" in params and params["x_axis"]:
        column_refs.append(("x_axis", params["x_axis"]))
    
    # Extract from scatter/bubble axis fields
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
    
    # Extract from gantt-specific fields
    for field in ["start_time", "end_time"]:
        if field in params and params[field]:
            column_refs.append((field, params[field]))
    
    # Extract from graph/sankey fields
    for field in ["source", "target"]:
        if field in params and params[field]:
            column_refs.append((field, params[field]))
    
    # Extract from wordcloud/bubble series
    for field in ["series"]:
        if field in params and params[field]:
            column_refs.append((field, params[field]))
    
    # Extract from map entity field
    if "entity" in params and params["entity"]:
        column_refs.append(("entity", params["entity"]))
    
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
    
    # Case-insensitive exact match
    for col in dataset_columns:
        col_name = col.get("column_name", "")
        if col_name.lower() == requested_lower:
            logger.info(f"Exact case-insensitive match found: '{requested_column}' -> '{col_name}'")
            return [col_name]
    
    # Fuzzy matching for typos
    available_names = [col.get("column_name", "") for col in dataset_columns]
    suggestions = get_close_matches(
        requested_lower,
        [name.lower() for name in available_names],
        n=max_suggestions,
        cutoff=0.6,
    )
    
    # Map back to original case
    original_cases = {}
    for name in available_names:
        original_cases[name.lower()] = name
    
    matched = [original_cases.get(s, s) for s in suggestions]
    
    if matched:
        logger.info(f"Fuzzy matches for '{requested_column}': {matched}")
    
    return matched


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
    
    result: Dict[str, Any] = {
        "is_valid": True,
        "missing_columns": [],
        "available_columns": [],
        "temporal_column_valid": True,
        "temporal_column_error": None,
        "errors": [],
        "warnings": [],
    }
    
    # Build lookup of available columns
    available_columns_lower = {}
    for col in dataset_columns:
        col_name = col.get("column_name", "")
        available_columns_lower[col_name.lower()] = col
    
    # Populate available_columns list
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
    
    # Extract all column references from params
    column_refs = _extract_columns_from_params(params, actual_viz_type)
    
    # Validate each column reference
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
            # For big_number with trendline, check if temporal_column is set
            if actual_viz_type == "big_number":
                # Big number with trendline needs a temporal x_axis
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
    
    # Title
    missing_count = len(validation_result.get("missing_columns", []))
    temporal_error = validation_result.get("temporal_column_error")
    
    if temporal_error:
        title_parts.append("Chart creation blocked: Temporal column validation failed")
    elif missing_count > 0:
        title_parts.append("Chart creation blocked: Missing required columns")
    else:
        title_parts.append("Chart creation blocked: Validation failed")
    
    title = " | ".join(title_parts) if title_parts else "Chart creation blocked"
    
    body_lines.append(f"")
    body_lines.append(f"Chart '{slice_name}' cannot be created - validation found issues:")
    body_lines.append(f"")
    
    # Missing columns section
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
                body_lines.append(f"   → Did you mean: {suggestions_str}?")
            else:
                body_lines.append(f"   → No close matches found in dataset")
            
            body_lines.append(f"")
    
    # Temporal column error
    temporal_error = validation_result.get("temporal_column_error")
    if temporal_error:
        body_lines.append(f"Temporal column error:")
        body_lines.append(f"  {temporal_error}")
        body_lines.append(f"")
    
    # Available columns
    available_columns = validation_result.get("available_columns", [])
    if available_columns:
        body_lines.append(f"Available columns in dataset (ID: {datasource_id}):")
        body_lines.append(f"")
        
        # Group by type
        temporal_cols = [c for c in available_columns if c.get("is_temporal")]
        non_temporal_cols = [c for c in available_columns if not c.get("is_temporal")]
        
        if temporal_cols:
            body_lines.append(f"  Temporal columns:")
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
    
    # Warnings
    warnings = validation_result.get("warnings", [])
    if warnings:
        body_lines.append(f"Warnings ({len(warnings)}):")
        for warning in warnings:
            body_lines.append(f"  - {warning}")
        body_lines.append(f"")
    
    # Action guidance
    body_lines.append(f"Fix:")
    if missing_columns:
        body_lines.append(f"  Update your chart params to use the correct column names shown above.")
    if temporal_error:
        body_lines.append(f"  Use a temporal (date/time) column for x_axis.")
    body_lines.append(f"  Then retry chart creation.")
    
    body = "\n".join(body_lines)
    
    logger.info(f"Formatted error message: {len(body)} characters")
    
    return {"title": title, "body": body}
