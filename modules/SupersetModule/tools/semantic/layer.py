"""
SemanticLayer class and table profiling for database introspection.

Provides the SemanticLayer class wrapper and the profile_table async function
for comprehensive table statistics generation.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from modules.SupersetModule.tools.semantic.helpers import (
    _classify_column,
    _extract_date,
    _extract_numeric,
    _extract_text,
    _quote,
    _resolve_columns,
    _run_row_count,
    _run_sql_and_get_data,
)
from modules.SupersetModule.tools.semantic.queries import (
    _build_date_sql,
    _build_numeric_sql,
    _build_text_sql,
    _build_top_values_sql,
)
from modules.metrics import get_metrics

logger = logging.getLogger(__name__)


class SemanticLayer:
    """
    Semantic layer for Apache Superset database introspection and profiling.

    Provides tools for analyzing database tables: column classification,
    statistical profiling, metric/dimension suggestion, and data dictionary
    generation.
    """

    def __init__(self, manager, server_id: str, database_id: int):
        """
        Initialize the semantic layer.

        Args:
            manager: The ConnectionManager instance.
            server_id: Superset server identifier.
            database_id: Superset database connection ID.
        """
        self.manager = manager
        self.server_id = server_id
        self.database_id = database_id

    async def profile_table(
        self,
        schema: str,
        table: str,
        columns: Optional[List[Dict[str, Any]]] = None,
        include_statistics: bool = True,
    ) -> str:
        """
        Generate comprehensive statistics for all columns in a database table.

        Args:
            schema: Database schema name (e.g. "public").
            table: Table name to profile.
            columns: Optional pre-fetched column list.
            include_statistics: If True, includes profiling stats.

        Returns:
            JSON string containing table profiling results.
        """
        return await profile_table(
            self.manager, self.server_id, self.database_id,
            schema, table, columns=columns,
        )

    async def suggest_metrics(self, schema: str, table: str) -> str:
        """Suggest metric columns for a table."""
        from modules.SupersetModule.tools.semantic.suggest import suggest_metrics
        return await suggest_metrics(self.manager, self.server_id, self.database_id, schema, table)

    async def suggest_dimensions(self, schema: str, table: str) -> str:
        """Suggest dimension columns for a table."""
        from modules.SupersetModule.tools.semantic.suggest import suggest_dimensions
        return await suggest_dimensions(self.manager, self.server_id, self.database_id, schema, table)

    async def get_data_dictionary(
        self, schema: str, table: str, include_statistics: bool = True
    ) -> str:
        """Generate a complete data dictionary for a database table."""
        from modules.SupersetModule.tools.semantic.dictionary import get_data_dictionary
        return await get_data_dictionary(
            self.manager, self.server_id, self.database_id,
            schema, table, include_statistics=include_statistics,
        )


async def profile_table(
    manager,
    server_id: str,
    database_id: int,
    schema: str,
    table: str,
    columns: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Generate comprehensive statistics for all columns in a database table.

    Profiles a table by computing row count, column counts, null statistics,
    min/max/avg/stddev for numeric columns, length stats for text columns,
    and min/max values for date columns. Also extracts top 10 most frequent
    values for up to 5 representative columns.

    Args:
        manager: The tool manager instance.
        server_id: Superset server identifier.
        database_id: Superset database connection ID.
        schema: Database schema name (e.g. "public").
        table: Table name to profile.
        columns: Optional pre-fetched column list.

    Returns:
        JSON string containing profiling results.
    """
    start_time = time.monotonic()
    resolved_cols, error = await _resolve_columns(manager, server_id, database_id, schema, table, columns)
    if error:
        return error
    columns = resolved_cols

    if not columns:
        return json.dumps({"error": True, "message": "No columns found"})

    numeric_cols = _extract_numeric(columns)
    text_cols = _extract_text(columns)
    date_cols = _extract_date(columns)
    all_cols = [c["column_name"] for c in columns]

    result: Dict[str, Any] = {
        "table": table,
        "schema": schema,
        "database_id": database_id,
        "total_columns": len(columns),
        "row_count": None,
        "numeric_columns": {},
        "text_columns": {},
        "date_columns": {},
        "other_columns": [c for c in columns if _classify_column(c["data_type"]) == "other"],
        "top_values": {},
    }

    row_count = await _run_row_count(manager, server_id, database_id, schema, table)
    result["row_count"] = row_count

    # Profile numeric columns
    if numeric_cols:
        sql = _build_numeric_sql(schema, table, numeric_cols)
        ok, data = await _run_sql_and_get_data(manager, server_id, database_id, sql, schema)
        if ok:
            for row in data:
                col_name = row.get("column_name")
                if col_name:
                    result["numeric_columns"][col_name] = _build_numeric_stats(row)

    # Profile text columns
    if text_cols:
        sql = _build_text_sql(schema, table, text_cols)
        ok, data = await _run_sql_and_get_data(manager, server_id, database_id, sql, schema)
        if ok:
            for row in data:
                col_name = row.get("column_name")
                if col_name:
                    result["text_columns"][col_name] = _build_text_stats(row)

    # Profile date columns
    if date_cols:
        sql = _build_date_sql(schema, table, date_cols)
        ok, data = await _run_sql_and_get_data(manager, server_id, database_id, sql, schema)
        if ok:
            for row in data:
                col_name = row.get("column_name")
                if col_name:
                    result["date_columns"][col_name] = _build_date_stats(row)

    # Get top 10 most frequent values for up to 5 columns
    top_cols = (numeric_cols + text_cols + date_cols)[:5]
    for col in top_cols:
        sql = _build_top_values_sql(schema, table, col, limit=10)
        ok, data = await _run_sql_and_get_data(manager, server_id, database_id, sql, schema)
        if ok:
            result["top_values"][col] = data

    mc = get_metrics()
    mc.tool_calls.labels(tool="semantic_profile_table", status="success").inc()
    mc.tool_duration.labels(tool="semantic_profile_table").observe(time.monotonic() - start_time)
    return json.dumps(result, indent=2, default=str)


def _build_numeric_stats(row: Dict[str, Any]) -> Dict[str, Any]:
    """Build numeric column stats from a row."""
    return {
        "data_type": "numeric",
        "total": int(row["total"]) if row.get("total") else 0,
        "non_null": int(row["non_null"]) if row.get("non_null") else 0,
        "null_count": int(row["null_count"]) if row.get("null_count") else 0,
        "null_pct": float(row["null_pct"]) if row.get("null_pct") else 0.0,
        "distinct_count": int(row["distinct_count"]) if row.get("distinct_count") else 0,
        "min": float(row["min_val"]) if row.get("min_val") is not None else None,
        "max": float(row["max_val"]) if row.get("max_val") is not None else None,
        "avg": float(row["avg_val"]) if row.get("avg_val") is not None else None,
        "stddev": float(row["stddev_val"]) if row.get("stddev_val") is not None else None,
    }


def _build_text_stats(row: Dict[str, Any]) -> Dict[str, Any]:
    """Build text column stats from a row."""
    return {
        "data_type": "text",
        "total": int(row["total"]) if row.get("total") else 0,
        "non_null": int(row["non_null"]) if row.get("non_null") else 0,
        "null_count": int(row["null_count"]) if row.get("null_count") else 0,
        "null_pct": float(row["null_pct"]) if row.get("null_pct") else 0.0,
        "distinct_count": int(row["distinct_count"]) if row.get("distinct_count") else 0,
        "min_length": int(row["min_length"]) if row.get("min_length") else 0,
        "max_length": int(row["max_length"]) if row.get("max_length") else 0,
        "avg_length": float(row["avg_length"]) if row.get("avg_length") else 0.0,
    }


def _build_date_stats(row: Dict[str, Any]) -> Dict[str, Any]:
    """Build date column stats from a row."""
    return {
        "data_type": "date",
        "total": int(row["total"]) if row.get("total") else 0,
        "non_null": int(row["non_null"]) if row.get("non_null") else 0,
        "null_count": int(row["null_count"]) if row.get("null_count") else 0,
        "null_pct": float(row["null_pct"]) if row.get("null_pct") else 0.0,
        "distinct_count": int(row["distinct_count"]) if row.get("distinct_count") else 0,
        "min": row.get("min_val"),
        "max": row.get("max_val"),
    }
