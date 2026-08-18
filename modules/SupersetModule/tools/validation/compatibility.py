"""
Datasource compatibility validation for Superset charts.

Provides validate_datasource_compatibility() which checks that chart params
are compatible with the datasource columns for each viz type.
"""

from typing import Any, Dict, List, Optional


def validate_datasource_compatibility(
    viz_type: str,
    params: Dict[str, Any],
    dataset_columns: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    """
    Validate that the datasource and params are compatible for the viz type.
        Checks datasource-level compatibility requirements by cross-referencing
        chart params against required/optional fields and column data types.
        Used as a secondary check after metric format validation.

    Args:
        viz_type: The Superset viz_type string (e.g. "bubble_v2", "heatmap_v2").
        params: Chart params dict to validate.
        dataset_columns: Optional list of column dicts from the dataset, used
            to verify column existence and data types (e.g., temporal vs. numeric).

    Returns:
        List of error message strings. Empty list means compatible.

    Checks:
        - world_map needs entity field
        - bubble_v2 needs x, y, size fields
        - heatmap_v2 needs x_axis and groupby
        - sunburst/treemap need groupby or columns for hierarchy
        - time series charts prefer temporal x_axis
        - big_number trendline needs temporal x_axis

        Examples:
            >>> cols = [{"column_name": "order_date", "type": "DATETIME"}]
            >>> errors = validate_datasource_compatibility("echarts_timeseries_line",
            ...     {"x_axis": "order_date", "granularity_sqla": "order_date"},
            ...     dataset_columns=cols)
            >>> errors  # x_axis is temporal — no errors
            []
            >>> errors = validate_datasource_compatibility("bubble_v2", {},
            ...     dataset_columns=cols)
            >>> errors  # bubble_v2 requires x, y, size fields
            ["Chart 'bubble_v2' requires field 'x'. ..."]
    """
    from .categories import DATASOURCE_REQUIREMENTS

    errors: List[str] = []
    reqs = DATASOURCE_REQUIREMENTS.get(viz_type)

    if not reqs:
        return errors

    required_fields = reqs.get("required", [])
    optional_fields = reqs.get("optional", [])
    description = reqs.get("description", "")

    for field in required_fields:
        if field == "entity":
            if not params.get("entity"):
                errors.append(
                    f"Chart '{viz_type}' requires 'entity' field. "
                    f"Add: 'entity': 'country_code' (or geographic identifier column). "
                    f"Dataset columns: {[c.get('column_name') for c in dataset_columns] if dataset_columns else 'unknown'}"
                )
        elif field == "groupby":
            if "groupby" not in params:
                errors.append(
                    f"Chart '{viz_type}' requires 'groupby' field. "
                    f"Add: 'groupby': '<column_name>' (dimension to categorize by)."
                )
        elif field in params:
            val = params[field]
            if isinstance(val, str) and not val.strip():
                errors.append(f"Chart '{viz_type}' field '{field}' is empty.")
            elif isinstance(val, list) and len(val) == 0:
                errors.append(f"Chart '{viz_type}' field '{field}' is an empty list.")
        else:
            errors.append(
                f"Chart '{viz_type}' requires field '{field}'. "
                f"Add it to params. {description}"
            )

    for field in optional_fields:
        if field == "entity":
            if "entity" not in params and viz_type == "world_map":
                pass
        elif field in params:
            val = params[field]
            if isinstance(val, str) and not val.strip():
                errors.append(f"Chart '{viz_type}' field '{field}' is empty.")

    if params.get("x_axis"):
        if dataset_columns:
            x_axis_lower = params["x_axis"].lower()
            col_exists = x_axis_lower in [c.get("column_name", "").lower() for c in dataset_columns]
            if not col_exists:
                errors.append(
                    f"Chart '{viz_type}' uses x_axis='{params['x_axis']}' which doesn't exist in dataset. "
                    f"Available columns: {[c.get('column_name') for c in dataset_columns]}"
                )
            elif reqs.get("x_axis_temporal"):
                x_axis_col = next((c for c in dataset_columns if c.get("column_name", "").lower() == x_axis_lower), None)
                if x_axis_col:
                    col_type = str(x_axis_col.get("type", "")).lower()
                    is_temporal = any(k in col_type for k in ["date", "time", "datetime", "timestamp", "temporal"])
                    if not is_temporal:
                        errors.append(
                            f"Chart '{viz_type}' uses x_axis='{params['x_axis']}' but it's not a date/time column. "
                            f"Found columns: {[c.get('column_name') for c in dataset_columns]}"
                        )

    if viz_type == "big_number" and params.get("x_axis") and dataset_columns:
        x_axis_lower = params["x_axis"].lower()
        if params.get("show_trend_line", False):
            x_axis_col = next((c for c in dataset_columns if c.get("column_name", "").lower() == x_axis_lower), None)
            if x_axis_col:
                col_type = str(x_axis_col.get("type", "")).lower()
                is_temporal = any(k in col_type for k in ["date", "time", "datetime", "timestamp", "temporal"])
                if not is_temporal:
                    errors.append(
                        f"Chart 'big_number' with trendline uses x_axis='{params['x_axis']}' but it's not a date/time column. "
                        f"Add a temporal column like 'order_date' or 'created_at'."
                    )

    return errors
