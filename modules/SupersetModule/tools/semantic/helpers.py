"""
Semantic layer utility functions for column classification and data profiling.

Contains helper functions for classifying column types, extracting
typed column lists, and executing SQL queries via Superset SQL Lab.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from modules.SupersetModule.tools.sqllab import sqllab_execute_query, sqllab_get_query_results

logger = logging.getLogger(__name__)

# PostgreSQL/standard database type keywords for column classification
NUMERIC_KEYWORDS = {
    "numeric", "integer", "bigint", "smallint", "decimal", "float",
    "double", "real", "int", "number", "serial", "bigserial",
    "smallserial", "money", "dec",
}

TEXT_KEYWORDS = {
    "string", "text", "varchar", "character varying", "char",
    "character", "text", "bpchar", "name", "uuid",
}

DATE_KEYWORDS = {
    "date", "timestamp", "timestamptz", "datetime", "time",
    "timetz", "interval", "timestamp without time zone",
    "timestamp with time zone",
}

BOOLEAN_KEYWORDS = {"boolean", "bool"}


def _quote(col: str) -> str:
    """Escape and quote a column name for use in SQL queries."""
    return f'"{col}"'


def _escape(val: str) -> str:
    """Escape single quotes in a string for safe embedding in SQL literals."""
    return val.replace("'", "''")


def _classify_column(data_type: str) -> str:
    """
    Classify a database column type into a semantic category.

    Maps a PostgreSQL data type string to one of: 'numeric', 'text', 'date',
    'boolean', or 'other'. Handles both exact matches and prefix matching.

    Args:
        data_type: PostgreSQL data type string (e.g. 'integer', 'varchar(255)').

    Returns:
        One of: 'numeric', 'text', 'date', 'boolean', 'other'.
    """
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


def _extract_numeric(columns: List[Dict[str, Any]]) -> List[str]:
    """Extract column names classified as numeric."""
    return [c["column_name"] for c in columns if _classify_column(c["data_type"]) == "numeric"]


def _extract_text(columns: List[Dict[str, Any]]) -> List[str]:
    """Extract column names classified as text."""
    return [c["column_name"] for c in columns if _classify_column(c["data_type"]) == "text"]


def _extract_date(columns: List[Dict[str, Any]]) -> List[str]:
    """Extract column names classified as date/time."""
    return [c["column_name"] for c in columns if _classify_column(c["data_type"]) == "date"]


def _is_metric_candidate(col: Dict[str, Any]) -> bool:
    """Check if a column is suitable as a metric (aggregatable numeric column)."""
    return _classify_column(col["data_type"]) == "numeric"


def _is_dimension_candidate(col: Dict[str, Any]) -> bool:
    """Check if a column is suitable as a dimension (groupable/filterable column)."""
    cat = _classify_column(col["data_type"])
    return cat in ("text", "boolean", "date") or cat == "other"


async def _run_sql_and_get_data(
    manager, server_id, database_id, sql: str, schema: Optional[str] = None
) -> Tuple[bool, Any]:
    """
    Execute a SQL query via Superset SQL Lab and retrieve results.

    Args:
        manager: The tool manager instance.
        server_id: Superset server identifier.
        database_id: Superset database connection ID.
        sql: SQL query to execute (must be a SELECT statement).
        schema: Optional database schema name.

    Returns:
        Tuple of (success: bool, data: list of rows or error message string).
    """
    try:
        exec_raw = await sqllab_execute_query(manager, server_id, database_id, sql, schema=schema)
        exec_data = json.loads(exec_raw)
        client_id = exec_data.get("result", {}).get("query", {}).get("client_id")
        if not client_id:
            return False, f"No client_id from execution: {exec_data}"
        await asyncio.sleep(1.5)
        results_raw = await sqllab_get_query_results(manager, server_id, client_id)
        results = json.loads(results_raw)
        rows = results.get("data", [])
        return True, rows
    except Exception as e:
        logger.warning(f"SQL profiling query failed: {e}")
        return False, str(e)


async def _run_row_count(manager, server_id, database_id, schema: str, table: str) -> Optional[int]:
    """Get the total row count for a table."""
    sql = f"SELECT COUNT(*) AS row_count FROM {_quote(schema)}.{_quote(table)}"
    ok, data = await _run_sql_and_get_data(manager, server_id, database_id, sql, schema)
    if ok and data:
        return int(data[0]["row_count"])
    return None


async def _resolve_columns(manager, server_id, database_id, schema: str, table: str, columns):
    """
    Resolve column list from schema if not provided.

    Returns (columns, error_result) tuple. If error_result is not None,
    an error occurred and should be returned to the caller.
    """
    from modules.SupersetModule.tools.datasets import get_database_schema as _get_schema

    if columns:
        return columns, None

    schema_raw = await _get_schema(manager, server_id, database_id, schema)
    try:
        schema_data = json.loads(schema_raw)
    except (json.JSONDecodeError, TypeError):
        return None, schema_raw if isinstance(schema_raw, str) else json.dumps({"error": True, "message": str(schema_raw)})

    tables = schema_data.get("tables", [])
    match = [t for t in tables if t.get("table_name", "").lower() == table.lower()]
    if not match:
        return None, json.dumps({"error": True, "message": f"Table '{table}' not found in schema '{schema}'"})
    return match[0].get("columns", []), None
