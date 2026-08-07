"""
Metric and dimension suggestion functions for semantic profiling.

Contains async functions for recommending metric columns (with aggregation
suggestions) and dimension columns (with usage hints) for database tables.
"""

import json
import logging
import time
from typing import Any, Dict

from modules.SupersetModule.tools.semantic.helpers import (
    _is_dimension_candidate,
    _is_metric_candidate,
    _resolve_columns,
)
from modules.metrics import get_metrics

logger = logging.getLogger(__name__)


async def suggest_metrics(
    manager,
    server_id: str,
    database_id: int,
    schema: str,
    table: str,
) -> str:
    """
    Suggest metric columns and their aggregation expressions for a table.

    Analyzes a table's schema to find all numeric columns and recommends
    standard aggregations (SUM, AVG, COUNT, MIN, MAX) for each.

    Args:
        manager: The tool manager instance.
        server_id: Superset server identifier.
        database_id: Superset database connection ID.
        schema: Database schema name.
        table: Table name.

    Returns:
        JSON string with table info and list of suggested metrics.
    """
    start_time = time.monotonic()
    resolved_cols, error = await _resolve_columns(manager, server_id, database_id, schema, table, None)
    if error:
        return error
    columns = resolved_cols

    candidates = [c for c in columns if _is_metric_candidate(c)]
    result = {
        "table": table,
        "schema": schema,
        "suggested_metrics": [],
    }
    for c in candidates:
        col = c["column_name"]
        result["suggested_metrics"].append({
            "column_name": col,
            "data_type": c.get("data_type", ""),
            "suggestions": [
                {"name": f"sum_{col}", "expression": f"SUM({col})", "type": "SUM"},
                {"name": f"avg_{col}", "expression": f"AVG({col})", "type": "AVG"},
                {"name": f"count_{col}", "expression": f"COUNT({col})", "type": "COUNT"},
                {"name": f"min_{col}", "expression": f"MIN({col})", "type": "MIN"},
                {"name": f"max_{col}", "expression": f"MAX({col})", "type": "MAX"},
            ],
        })
    mc = get_metrics()
    mc.tool_calls.labels(tool="semantic_suggest_metrics", status="success").inc()
    mc.tool_duration.labels(tool="semantic_suggest_metrics").observe(time.monotonic() - start_time)
    return json.dumps(result, indent=2)


async def suggest_dimensions(
    manager,
    server_id: str,
    database_id: int,
    schema: str,
    table: str,
) -> str:
    """
    Suggest dimension columns and their recommended usage for a table.

    Analyzes a table's schema to find text, date, boolean, and other columns
    suitable for grouping, filtering, or slicing in charts.

    Args:
        manager: The tool manager instance.
        server_id: Superset server identifier.
        database_id: Superset database connection ID.
        schema: Database schema name.
        table: Table name.

    Returns:
        JSON string with table info and list of suggested dimension columns.
    """
    start_time = time.monotonic()
    resolved_cols, error = await _resolve_columns(manager, server_id, database_id, schema, table, None)
    if error:
        return error
    columns = resolved_cols

    candidates = [c for c in columns if _is_dimension_candidate(c)]
    result = {
        "table": table,
        "schema": schema,
        "suggested_dimensions": [],
    }
    for c in candidates:
        cat = _classify_column(c["data_type"])
        col = c["column_name"]
        suggestion = {
            "column_name": col,
            "data_type": c.get("data_type", ""),
            "category": cat,
        }
        if cat == "text":
            suggestion["usage"] = "Group By / Filter / Slice"
            suggestion["example_aggregations"] = ["COUNT(DISTINCT)", "COUNT(*)"]
        elif cat == "date":
            suggestion["usage"] = "Time range filter / Trend axis"
            suggestion["example_aggregations"] = ["DATE_TRUNC('month', ...)", "EXTRACT(YEAR FROM ...)"]
        elif cat == "boolean":
            suggestion["usage"] = "Flag filter / Segmentation"
            suggestion["example_aggregations"] = ["COUNT(*)", "SUM(CASE WHEN ...)"]
        result["suggested_dimensions"].append(suggestion)
    mc = get_metrics()
    mc.tool_calls.labels(tool="semantic_suggest_dimensions", status="success").inc()
    mc.tool_duration.labels(tool="semantic_suggest_dimensions").observe(time.monotonic() - start_time)
    return json.dumps(result, indent=2)


def _classify_column(data_type: str) -> str:
    """Classify a database column type into a semantic category."""
    from modules.SupersetModule.tools.semantic.helpers import (
        BOOLEAN_KEYWORDS, DATE_KEYWORDS, NUMERIC_KEYWORDS, TEXT_KEYWORDS,
    )
    dt = data_type.lower().strip()
    if dt in NUMERIC_KEYWORDS:
        return "numeric"
    if dt in TEXT_KEYWORDS or dt.startswith("varchar") or dt.startswith("character"):
        return "text"
    if dt in DATE_KEYWORDS or dt.startswith("timestamp") or dt.startswith("date"):
        return "date"
    if dt in BOOLEAN_KEYWORDS:
        return "boolean"
    return "other"
