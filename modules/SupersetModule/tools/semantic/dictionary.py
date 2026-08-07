"""
Data dictionary generation for semantic profiling.

Contains the async function to generate a complete data dictionary for
a database table with column metadata, classification, and optional stats.
"""

import json
import logging
import time
from typing import Any, Dict

from modules.SupersetModule.tools.semantic.helpers import _classify_column, _resolve_columns
from modules.metrics import get_metrics

logger = logging.getLogger(__name__)


async def get_data_dictionary(
    manager,
    server_id: str,
    database_id: int,
    schema: str,
    table: str,
    include_statistics: bool = True,
) -> str:
    """
    Generate a complete data dictionary for a database table.

    Creates a comprehensive data dictionary listing all columns with their
    data types, semantic categories, recommended roles (metric/dimension),
    suggested aggregations/uses, and optional profiling statistics.

    Args:
        manager: The tool manager instance.
        server_id: Superset server identifier.
        database_id: Superset database connection ID.
        schema: Database schema name.
        table: Table name.
        include_statistics: If True, includes profiling stats from profile_table.

    Returns:
        JSON string with table metadata and per-column entries.
    """
    start_time = time.monotonic()
    resolved_cols, error = await _resolve_columns(manager, server_id, database_id, schema, table, None)
    if error:
        return error
    columns = resolved_cols

    # Optionally fetch profiling statistics for all columns
    profile = {}
    if include_statistics:
        from modules.SupersetModule.tools.semantic.layer import profile_table
        profile_raw = await profile_table(manager, server_id, database_id, schema, table, columns=columns)
        try:
            profile = json.loads(profile_raw)
        except (json.JSONDecodeError, TypeError):
            pass

    # Build the data dictionary structure
    dictionary: Dict[str, Any] = {
        "table": table,
        "schema": schema,
        "database_id": database_id,
        "row_count": profile.get("row_count") if include_statistics else None,
        "columns": [],
    }

    # Process each column and add metadata
    for col in columns:
        col_name = col["column_name"]
        col_type = col.get("data_type", "")
        cat = _classify_column(col_type)
        entry: Dict[str, Any] = {
            "column_name": col_name,
            "data_type": col_type,
            "category": cat,
        }
        if cat == "numeric":
            entry["recommended_role"] = "metric"
            entry["suggested_aggregations"] = ["SUM", "AVG", "MIN", "MAX", "COUNT"]
        elif cat == "text":
            entry["recommended_role"] = "dimension"
            entry["suggested_uses"] = ["group by", "filter", "label"]
        elif cat == "date":
            entry["recommended_role"] = "dimension"
            entry["suggested_uses"] = ["time range", "trend", "period comparison"]

        # Merge profiling statistics if available
        if include_statistics:
            stats = (
                profile.get("numeric_columns", {}).get(col_name)
                or profile.get("text_columns", {}).get(col_name)
                or profile.get("date_columns", {}).get(col_name)
            )
            if stats:
                entry["statistics"] = stats

        dictionary["columns"].append(entry)

    mc = get_metrics()
    mc.tool_calls.labels(tool="semantic_get_data_dictionary", status="success").inc()
    mc.tool_duration.labels(tool="semantic_get_data_dictionary").observe(time.monotonic() - start_time)
    return json.dumps(dictionary, indent=2, default=str)
