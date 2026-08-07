"""
Chart type resolution and column extraction utilities.

Contains _resolve_viz_type, _extract_columns_from_dataset_response,
_extract_chart_ids_from_position_json, _validate_sankey_params.
"""

import os
import json
import re
import logging
from typing import List, Dict, Any, Optional
from modules.SupersetModule.chart_strategies import TYPE_MAP
from modules.SupersetModule.superset_validation import validate_chart_params
from modules.metrics import get_metrics

logger = logging.getLogger(__name__)


def _resolve_viz_type(viz_type: str) -> str:
    """
    Resolve a generic/human-friendly viz_type alias to the actual Superset viz_type string.

    Maps common shorthand names (e.g., 'bar', 'line', 'table') to their full
    Superset equivalents (e.g., 'echarts_bar', 'echarts_timeseries_line', 'table').
    This allows users to specify chart types using familiar names.

    Args:
        viz_type: A chart type name, which may be a shorthand alias
            (e.g., 'bar', 'line', 'pie', 'table', 'scatter') or a full
            Superset viz_type string.

    Returns:
        The resolved Superset viz_type string. If the input is not a known
        alias, returns the input unchanged (pass-through for full viz_types).
    """
    return TYPE_MAP.get(viz_type, viz_type)


def _extract_columns_from_dataset_response(response_str: str) -> List[Dict[str, Any]]:
    """
    Extract the columns list from a JSON-encoded Superset dataset API response.

    Parses the response body from GET /api/v1/dataset/{id} and returns the
    'columns' array, which contains column metadata (name, type, etc.)
    for use in chart validation.

    Args:
        response_str: Raw JSON string response from the Superset dataset API.
            Expected format: {"result": {"columns": [...], "metrics": [...]}}

    Returns:
        List of column dicts from the dataset response. Returns empty list
        if parsing fails or no columns are found.
    """
    try:
        data = json.loads(response_str)
        result = data.get("result", {})
        if isinstance(result, dict):
            columns = result.get("columns", [])
            if isinstance(columns, list):
                return columns
        return []
    except (json.JSONDecodeError, TypeError):
        return []


def _extract_chart_ids_from_position_json(position_json: str) -> List[int]:
    """
    Extract all chart IDs from a position JSON string.

    Recursively walks the position_json structure to find all nodes
    containing a ``slice_id`` key (the legacy Superset format for
    embedding chart references within dashboard layout trees).

    Args:
        position_json: Raw JSON string of the dashboard position layout.

    Returns:
        List of integer chart (slice) IDs found in the layout.
    """
    chart_ids = []
    try:
        if isinstance(position_json, str):
            pos = json.loads(position_json)
        else:
            pos = position_json

        def walk(obj):
            """Recursively traverse dicts/lists to find slice_id entries."""
            if isinstance(obj, dict):
                if "slice_id" in obj and isinstance(obj["slice_id"], int):
                    chart_ids.append(obj["slice_id"])
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(pos)
    except (json.JSONDecodeError, TypeError):
        pass

    return chart_ids


def _validate_sankey_params(params: Dict[str, Any], slice_name: str) -> Optional[Dict[str, str]]:
    """
    Validate Sankey chart params and return warning if potential cycle detected.

    Sankey charts require a DAG (directed acyclic graph). If source/target
    columns have circular references, Superset will error at render time.
    We validate params structure and suggest the cycle-breaking SQL fix.

    Args:
        params: Chart params dict containing Sankey-specific fields
            ('source', 'target') and viz_type='sankey_v2'.
        slice_name: Name of the chart (used in warning title).

    Returns:
        Dict with 'title' and 'body' keys if warnings/errors found, or None
        if the params are valid (or are not for a Sankey chart).
    """
    if "sankey_v2" not in params.get("viz_type", ""):
        return None

    errors = []

    validation_errors = validate_chart_params("sankey_v2", params)
    if validation_errors:
        errors.extend(validation_errors)

    if errors:
        return {"title": f"Chart '{slice_name}' - Sankey validation errors",
                "body": "\n".join(errors) + "\n\nSankey charts require 'source' and 'target' fields."}

    if params.get("_cycle_fix_suggested"):
        return None

    source_col = params.get("source", "unknown")
    target_col = params.get("target", "unknown")

    return {
        "title": f"Chart '{slice_name}' - Sankey cycle fix needed",
        "body": (
            f"Sankey chart uses source='{source_col}', target='{target_col}'.\n\n"
            f"To prevent 'Sankey is a DAG, the original data has cycle!' errors, "
            f"add this to your dataset SQL:\n\n"
            f"HAVING {source_col} <> {target_col} AND {source_col} < {target_col}\n\n"
            f"This ensures lexicographic ordering breaks all graph cycles."
        )
    }
