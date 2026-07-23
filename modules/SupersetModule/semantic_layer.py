"""
Semantic layer for Apache Superset database introspection and profiling.

Description:
    Provides tools for analyzing database tables: column classification, statistical
    profiling, metric/dimension suggestion, and data dictionary generation. All functions
    execute SQL queries against PostgreSQL/MariaDB databases via Superset's SQL Lab.

Modules:
    - Column classification: Classifies columns as numeric, text, date, boolean, or other
    - Table profiling: Generates statistics (count, null%, min/max/avg, distinct, stddev)
    - Metric suggestion: Recommends aggregatable columns with SUM/AVG/COUNT/MIN/MAX
    - Dimension suggestion: Recommends grouping/filtering columns with usage hints
    - Data dictionary: Full table metadata with classification and optional statistics
"""
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from modules.SupersetModule.tools.sqllab import sqllab_execute_query, sqllab_get_query_results
from modules.SupersetModule.tools.datasets import get_database_schema as _get_schema
from modules.metrics import get_metrics

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


def _classify_column(data_type: str) -> str:
    """
    Classify a database column type into a semantic category.

    Description:
        Maps a PostgreSQL data type string to one of: 'numeric', 'text', 'date',
        'boolean', or 'other'. Handles both exact matches and prefix matching
        (e.g., 'varchar(255)' matches via startswith).

    Args:
        data_type: PostgreSQL data type string (e.g. 'integer', 'varchar(255)', 'timestamp without time zone').

    Returns:
        One of: 'numeric', 'text', 'date', 'boolean', 'other'.
    """
    dt = data_type.lower().strip()
    # Check exact matches against keyword sets for fast classification
    if dt in NUMERIC_KEYWORDS:
        return "numeric"
    # Text types: exact match or prefix match for parameterized types like varchar(255)
    if dt in TEXT_KEYWORDS or dt.startswith("varchar") or dt.startswith("character"):
        return "text"
    # Date/time types: exact match or prefix match for timestamp variants
    if dt in DATE_KEYWORDS or dt.startswith("timestamp") or dt.startswith("date"):
        return "date"
    # Boolean: must match exactly (no parameterized variants)
    if dt in BOOLEAN_KEYWORDS:
        return "boolean"
    # Default fallback for unsupported or unknown types (JSON, arrays, enums, etc.)
    return "other"


def _extract_numeric(columns: List[Dict[str, Any]]) -> List[str]:
    """
    Extract column names classified as numeric.

    Args:
        columns: List of column dicts with 'data_type' keys.

    Returns:
        List of column names where data_type classifies as 'numeric'.
    """
    # Filter columns by classification: keep only those identified as numeric types
    return [c["column_name"] for c in columns if _classify_column(c["data_type"]) == "numeric"]


def _extract_text(columns: List[Dict[str, Any]]) -> List[str]:
    """
    Extract column names classified as text.

    Args:
        columns: List of column dicts with 'data_type' keys.

    Returns:
        List of column names where data_type classifies as 'text'.
    """
    # Filter columns by classification: keep only those identified as text types
    return [c["column_name"] for c in columns if _classify_column(c["data_type"]) == "text"]


def _extract_date(columns: List[Dict[str, Any]]) -> List[str]:
    """
    Extract column names classified as date/time.

    Args:
        columns: List of column dicts with 'data_type' keys.

    Returns:
        List of column names where data_type classifies as 'date'.
    """
    # Filter columns by classification: keep only those identified as date/time types
    return [c["column_name"] for c in columns if _classify_column(c["data_type"]) == "date"]


def _quote(col: str) -> str:
    """
    Escape and quote a column name for use in SQL queries.

    Args:
        col: Column name to quote.

    Returns:
        Column name wrapped in double quotes (SQL standard identifier quoting).
    """
    # Wrap in double quotes per SQL standard; preserves case sensitivity
    return f'"{col}"'


def _escape(val: str) -> str:
    """
    Escape single quotes in a string for safe embedding in SQL literals.

    Args:
        val: String value to escape.

    Returns:
        String with all single quotes doubled (SQL standard escape).
    """
    # Double all single quotes to prevent SQL injection / syntax errors
    return val.replace("'", "''")


def _build_numeric_sql(schema: str, table: str, columns: List[str]) -> str:
    """
    Build a SQL query that generates statistics for numeric columns.

    Description:
        Creates a UNION ALL query that computes total rows, non-null count,
        null percentage, distinct count, min, max, avg, and standard deviation
        for each specified numeric column.

    Args:
        schema: Database schema name.
        table: Table name.
        columns: List of numeric column names.

    Returns:
        SQL query string with UNION ALL subqueries, one per column.
        Returns empty string if columns list is empty.
    """
    if not columns:
        return ""
    unions = []
    for col in columns:
        q = _quote(col)  # Quote column name for SQL safety
        # Build a subquery for this column's statistics
        unions.append(f"""SELECT
  '{_escape(col)}' AS column_name,
  'numeric' AS data_type,
  COUNT(*) AS total,
  COUNT({q}) AS non_null,
  COUNT(*) - COUNT({q}) AS null_count,
  ROUND((COUNT(*) - COUNT({q})) * 100.0 / NULLIF(COUNT(*), 0), 2) AS null_pct,
  COUNT(DISTINCT {q}) AS distinct_count,
  ROUND(MIN({q})::numeric, 6) AS min_val,
  ROUND(MAX({q})::numeric, 6) AS max_val,
  ROUND(AVG({q})::numeric, 6) AS avg_val,
  ROUND(COALESCE(STDDEV({q}), 0)::numeric, 6) AS stddev_val
FROM {_quote(schema)}.{_quote(table)}""")
    # Join all column subqueries with UNION ALL to produce a single result set
    return "\nUNION ALL\n".join(unions)


def _build_text_sql(schema: str, table: str, columns: List[str]) -> str:
    """
    Build a SQL query that generates statistics for text columns.

    Description:
        Creates a UNION ALL query that computes total rows, non-null count,
        null percentage, distinct count, and string length statistics (min/max/avg).

    Args:
        schema: Database schema name.
        table: Table name.
        columns: List of text column names.

    Returns:
        SQL query string with UNION ALL subqueries, one per column.
        Returns empty string if columns list is empty.
    """
    if not columns:
        return ""
    unions = []
    for col in columns:
        q = _quote(col)
        # Build a subquery for text column statistics (length-based)
        unions.append(f"""SELECT
  '{_escape(col)}' AS column_name,
  'text' AS data_type,
  COUNT(*) AS total,
  COUNT({q}) AS non_null,
  COUNT(*) - COUNT({q}) AS null_count,
  ROUND((COUNT(*) - COUNT({q})) * 100.0 / NULLIF(COUNT(*), 0), 2) AS null_pct,
  COUNT(DISTINCT {q}) AS distinct_count,
  ROUND(MIN(LENGTH(CAST({q} AS TEXT)))::numeric, 0) AS min_length,
  ROUND(MAX(LENGTH(CAST({q} AS TEXT)))::numeric, 0) AS max_length,
  ROUND(AVG(LENGTH(CAST({q} AS TEXT)))::numeric, 2) AS avg_length
FROM {_quote(schema)}.{_quote(table)}""")
    # Join all column subqueries with UNION ALL for a single result set
    return "\nUNION ALL\n".join(unions)


def _build_date_sql(schema: str, table: str, columns: List[str]) -> str:
    """
    Build a SQL query that generates statistics for date/time columns.

    Description:
        Creates a UNION ALL query that computes total rows, non-null count,
        null percentage, distinct count, and min/max date values.

    Args:
        schema: Database schema name.
        table: Table name.
        columns: List of date column names.

    Returns:
        SQL query string with UNION ALL subqueries, one per column.
        Returns empty string if columns list is empty.
    """
    if not columns:
        return ""
    unions = []
    for col in columns:
        q = _quote(col)
        # Build a subquery for date column statistics (min/max values)
        unions.append(f"""SELECT
  '{_escape(col)}' AS column_name,
  'date' AS data_type,
  COUNT(*) AS total,
  COUNT({q}) AS non_null,
  COUNT(*) - COUNT({q}) AS null_count,
  ROUND((COUNT(*) - COUNT({q})) * 100.0 / NULLIF(COUNT(*), 0), 2) AS null_pct,
  COUNT(DISTINCT {q}) AS distinct_count,
  MIN({q})::TEXT AS min_val,
  MAX({q})::TEXT AS max_val
FROM {_quote(schema)}.{_quote(table)}""")
    # Join all column subqueries with UNION ALL for a single result set
    return "\nUNION ALL\n".join(unions)


def _build_top_values_sql(schema: str, table: str, column: str, limit: int = 10) -> str:
    """
    Build a SQL query to find the most frequent values in a column.

    Description:
        Returns the top N values by frequency with percentage of total,
        useful for understanding data distribution and identifying common values.

    Args:
        schema: Database schema name.
        table: Table name.
        column: Column name to analyze.
        limit: Maximum number of top values to return (default 10).

    Returns:
        SQL query string returning top values with frequency and percentage.
    """
    q = _quote(column)
    # Use window function SUM(COUNT(*)) OVER() to calculate percentage of total
    return f"""SELECT
  '{_escape(column)}' AS column_name,
  {q} AS value,
  COUNT(*) AS frequency,
  ROUND(COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER(), 0), 2) AS pct
FROM {_quote(schema)}.{_quote(table)}
WHERE {q} IS NOT NULL
GROUP BY {q}
ORDER BY frequency DESC
LIMIT {limit}"""


async def _run_sql_and_get_data(
    manager, server_id, database_id, sql: str, schema: Optional[str] = None
) -> Tuple[bool, Any]:
    """
    Execute a SQL query via Superset SQL Lab and retrieve results.

    Description:
        Internal helper that executes a SQL query through Superset's SQL Lab API,
        waits for execution to complete, and retrieves the result rows.

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
        # Execute the SQL query via Superset SQL Lab API
        exec_raw = await sqllab_execute_query(
            manager, server_id, database_id, sql, schema=schema
        )
        exec_data = json.loads(exec_raw)
        # Extract the client_id needed to retrieve results
        client_id = exec_data.get("result", {}).get("query", {}).get("client_id")
        if not client_id:
            return False, f"No client_id from execution: {exec_data}"
        # Wait for query execution to complete (async sleep)
        import asyncio
        await asyncio.sleep(1.5)
        # Retrieve the query results using the client_id
        results_raw = await sqllab_get_query_results(manager, server_id, client_id)
        results = json.loads(results_raw)
        # Extract the actual data rows from the result envelope
        rows = results.get("data", [])
        return True, rows
    except Exception as e:
        # Log failures and return error info without crashing the caller
        logger.warning(f"SQL profiling query failed: {e}")
        return False, str(e)


async def _run_row_count(
    manager, server_id, database_id, schema: str, table: str
) -> Optional[int]:
    """
    Get the total row count for a table.

    Args:
        manager: The tool manager instance.
        server_id: Superset server identifier.
        database_id: Superset database connection ID.
        schema: Database schema name.
        table: Table name.

    Returns:
        Row count as integer, or None if query failed.
    """
    # Build a simple COUNT(*) query against the target table
    sql = f"SELECT COUNT(*) AS row_count FROM {_quote(schema)}.{_quote(table)}"
    ok, data = await _run_sql_and_get_data(manager, server_id, database_id, sql, schema)
    if ok and data:
        # Extract the count from the first row's row_count column
        return int(data[0]["row_count"])
    return None


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

    Description:
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
        columns: Optional pre-fetched column list. If None, schema is fetched from Superset.

    Returns:
        JSON string containing: table, schema, row_count, numeric_columns stats,
        text_columns stats, date_columns stats, other_columns list, and top_values.

    Example output structure:
        {
            "table": "orders",
            "schema": "public",
            "row_count": 150000,
            "numeric_columns": {
                "sales": {"total": 150000, "non_null": 149000, "null_pct": 0.67,
                          "min": 10.0, "max": 50000.0, "avg": 234.56, "stddev": 120.3}
            },
            "top_values": {"product_line": [...]}
        }
    """
    start_time = time.monotonic()
    if not columns:
        # Fetch schema from Superset to get column definitions
        schema_raw = await _get_schema(manager, server_id, database_id, schema)
        try:
            schema_data = json.loads(schema_raw)
        except (json.JSONDecodeError, TypeError):
            return schema_raw if isinstance(schema_raw, str) else json.dumps({"error": True, "message": str(schema_raw)})
        # Locate the target table within the schema data
        tables = schema_data.get("tables", [])
        match = [t for t in tables if t.get("table_name", "").lower() == table.lower()]
        if not match:
            return json.dumps({"error": True, "message": f"Table '{table}' not found in schema '{schema}'"})
        columns = match[0].get("columns", [])

    if not columns:
        return json.dumps({"error": True, "message": "No columns found"})

    # Classify columns into numeric, text, and date categories
    numeric_cols = _extract_numeric(columns)
    text_cols = _extract_text(columns)
    date_cols = _extract_date(columns)
    all_cols = [c["column_name"] for c in columns]

    # Initialize result structure with sectioned column type containers
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

    # Fetch row count with a simple COUNT(*) query
    row_count = await _run_row_count(manager, server_id, database_id, schema, table)
    result["row_count"] = row_count

    # Profile numeric columns: compute count, null%, distinct, min, max, avg, stddev
    if numeric_cols:
        sql = _build_numeric_sql(schema, table, numeric_cols)
        ok, data = await _run_sql_and_get_data(manager, server_id, database_id, sql, schema)
        if ok:
            # Populate numeric_columns dict from the UNION ALL result rows
            for row in data:
                col_name = row.get("column_name")
                if col_name:
                    result["numeric_columns"][col_name] = {
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

    # Profile text columns: compute count, null%, distinct, min/max/avg length
    if text_cols:
        sql = _build_text_sql(schema, table, text_cols)
        ok, data = await _run_sql_and_get_data(manager, server_id, database_id, sql, schema)
        if ok:
            # Populate text_columns dict from the UNION ALL result rows
            for row in data:
                col_name = row.get("column_name")
                if col_name:
                    result["text_columns"][col_name] = {
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

    # Profile date columns: compute count, null%, distinct, min/max values
    if date_cols:
        sql = _build_date_sql(schema, table, date_cols)
        ok, data = await _run_sql_and_get_data(manager, server_id, database_id, sql, schema)
        if ok:
            # Populate date_columns dict from the UNION ALL result rows
            for row in data:
                col_name = row.get("column_name")
                if col_name:
                    result["date_columns"][col_name] = {
                        "data_type": "date",
                        "total": int(row["total"]) if row.get("total") else 0,
                        "non_null": int(row["non_null"]) if row.get("non_null") else 0,
                        "null_count": int(row["null_count"]) if row.get("null_count") else 0,
                        "null_pct": float(row["null_pct"]) if row.get("null_pct") else 0.0,
                        "distinct_count": int(row["distinct_count"]) if row.get("distinct_count") else 0,
                        "min": row.get("min_val"),
                        "max": row.get("max_val"),
                    }

    # Get top 10 most frequent values for up to 5 columns (mix of numeric, text, date)
    top_cols = (numeric_cols + text_cols + date_cols)[:5]
    for col in top_cols:
        sql = _build_top_values_sql(schema, table, col, limit=10)
        ok, data = await _run_sql_and_get_data(manager, server_id, database_id, sql, schema)
        if ok:
            result["top_values"][col] = data

    # Record metrics and return JSON result
    mc = get_metrics()
    mc.tool_calls.labels(tool="semantic_profile_table", status="success").inc()
    mc.tool_duration.labels(tool="semantic_profile_table").observe(time.monotonic() - start_time)
    return json.dumps(result, indent=2, default=str)


def _is_metric_candidate(col: Dict[str, Any]) -> bool:
    """
    Check if a column is suitable as a metric (aggregatable numeric column).

    Args:
        col: Column dict with 'data_type' key.

    Returns:
        True if the column is classified as 'numeric'.
    """
    return _classify_column(col["data_type"]) == "numeric"


def _is_dimension_candidate(col: Dict[str, Any]) -> bool:
    """
    Check if a column is suitable as a dimension (groupable/filterable column).

    Args:
        col: Column dict with 'data_type' key.

    Returns:
        True if the column is classified as text, boolean, date, or other.
    """
    cat = _classify_column(col["data_type"])
    return cat in ("text", "boolean", "date") or cat == "other"


async def suggest_metrics(
    manager,
    server_id: str,
    database_id: int,
    schema: str,
    table: str,
) -> str:
    """
    Suggest metric columns and their aggregation expressions for a table.

    Description:
        Analyzes a table's schema to find all numeric columns and recommends
        standard aggregations (SUM, AVG, COUNT, MIN, MAX) for each.

    Args:
        manager: The tool manager instance.
        server_id: Superset server identifier.
        database_id: Superset database connection ID.
        schema: Database schema name.
        table: Table name.

    Returns:
        JSON string with table info and list of suggested metrics per numeric column.
    """
    start_time = time.monotonic()
    # Fetch schema from Superset to get column definitions
    schema_raw = await _get_schema(manager, server_id, database_id, schema)
    try:
        schema_data = json.loads(schema_raw)
    except (json.JSONDecodeError, TypeError):
        return schema_raw if isinstance(schema_raw, str) else json.dumps({"error": True, "message": str(schema_raw)})
    # Locate the target table within the schema data
    tables = schema_data.get("tables", [])
    match = [t for t in tables if t.get("table_name", "").lower() == table.lower()]
    if not match:
        return json.dumps({"error": True, "message": f"Table '{table}' not found"})
    columns = match[0].get("columns", [])

    # Filter to only numeric columns (metric candidates)
    candidates = [c for c in columns if _is_metric_candidate(c)]
    result = {
        "table": table,
        "schema": schema,
        "suggested_metrics": [],
    }
    # Generate aggregation suggestions for each numeric column
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
    # Record metrics for monitoring and return result
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

    Description:
        Analyzes a table's schema to find text, date, boolean, and other columns
        suitable for grouping, filtering, or slicing in charts. Provides usage
        hints and example SQL aggregations for each category.

    Args:
        manager: The tool manager instance.
        server_id: Superset server identifier.
        database_id: Superset database connection ID.
        schema: Database schema name.
        table: Table name.

    Returns:
        JSON string with table info and list of suggested dimension columns
        with category, usage hints, and example aggregations.
    """
    start_time = time.monotonic()
    # Fetch schema from Superset to get column definitions
    schema_raw = await _get_schema(manager, server_id, database_id, schema)
    try:
        schema_data = json.loads(schema_raw)
    except (json.JSONDecodeError, TypeError):
        return schema_raw if isinstance(schema_raw, str) else json.dumps({"error": True, "message": str(schema_raw)})
    # Locate the target table within the schema data
    tables = schema_data.get("tables", [])
    match = [t for t in tables if t.get("table_name", "").lower() == table.lower()]
    if not match:
        return json.dumps({"error": True, "message": f"Table '{table}' not found"})
    columns = match[0].get("columns", [])

    # Filter to dimension candidates (text, boolean, date, other)
    candidates = [c for c in columns if _is_dimension_candidate(c)]
    result = {
        "table": table,
        "schema": schema,
        "suggested_dimensions": [],
    }
    # Generate dimension suggestions with usage hints per category
    for c in candidates:
        cat = _classify_column(c["data_type"])
        col = c["column_name"]
        suggestion = {
            "column_name": col,
            "data_type": c.get("data_type", ""),
            "category": cat,
        }
        # Add category-specific usage hints and example SQL
        if cat == "text":
            suggestion["usage"] = "Group By / Filter / Slice"
            suggestion["example_aggregations"] = ["COUNT(DISTINCT)", "COUNT(*)"]
        elif cat == "date":
            suggestion["usage"] = "Time range filter / Trend axis"
            suggestion["example_aggregations"] = ["DATE_TRUNC('month', ...)", "EXTRACT(YEAR FROM ...)"]
        elif cat == "boolean":
            suggestion["usage"] = "Flag filter / Segmentation"
            suggestion["example_aggregations"] = ["COUNT(*)", "SUM(CASE WHEN ...)"]
        # Append the suggestion entry to the results list
        result["suggested_dimensions"].append(suggestion)
    # Record metrics for monitoring and return result
    mc = get_metrics()
    mc.tool_calls.labels(tool="semantic_suggest_dimensions", status="success").inc()
    mc.tool_duration.labels(tool="semantic_suggest_dimensions").observe(time.monotonic() - start_time)
    return json.dumps(result, indent=2)


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

    Description:
        Creates a comprehensive data dictionary listing all columns with their
        data types, semantic categories, recommended roles (metric/dimension),
        suggested aggregations/uses, and optional profiling statistics.

    Args:
        manager: The tool manager instance.
        server_id: Superset server identifier.
        database_id: Superset database connection ID.
        schema: Database schema name.
        table: Table name.
        include_statistics: If True, includes profiling stats (count, null%, min/max/avg) from profile_table.

    Returns:
        JSON string with table metadata, row count, and per-column entries containing
        column_name, data_type, category, recommended_role, suggested_aggregations/uses,
        and optional statistics.
    """
    start_time = time.monotonic()
    # Fetch schema from Superset to get column definitions
    schema_raw = await _get_schema(manager, server_id, database_id, schema)
    try:
        schema_data = json.loads(schema_raw)
    except (json.JSONDecodeError, TypeError):
        return schema_raw if isinstance(schema_raw, str) else json.dumps({"error": True, "message": str(schema_raw)})
    # Locate the target table within the schema data
    tables = schema_data.get("tables", [])
    match = [t for t in tables if t.get("table_name", "").lower() == table.lower()]
    if not match:
        return json.dumps({"error": True, "message": f"Table '{table}' not found"})
    columns = match[0].get("columns", [])

    # Optionally fetch profiling statistics for all columns
    profile = {}
    if include_statistics:
        profile_raw = await profile_table(manager, server_id, database_id, schema, table, columns=columns)
        try:
            profile = json.loads(profile_raw)
        except (json.JSONDecodeError, TypeError):
            pass

    # Build the data dictionary structure
    dictionary = {
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
        # Add role recommendation based on category
        if cat == "numeric":
            entry["recommended_role"] = "metric"
            entry["suggested_aggregations"] = ["SUM", "AVG", "MIN", "MAX", "COUNT"]
        elif cat == "text":
            entry["recommended_role"] = "dimension"
            entry["suggested_uses"] = ["group by", "filter", "label"]
        elif cat == "date":
            entry["recommended_role"] = "dimension"
            entry["suggested_uses"] = ["time range", "trend", "period comparison"]
        # Merge profiling statistics if available (matches by column name)
        if include_statistics:
            stats = (
                profile.get("numeric_columns", {}).get(col_name)
                or profile.get("text_columns", {}).get(col_name)
                or profile.get("date_columns", {}).get(col_name)
            )
            if stats:
                entry["statistics"] = stats
        # Append the fully-built column entry to the dictionary
        dictionary["columns"].append(entry)

    # Record metrics for monitoring and return result
    mc = get_metrics()
    mc.tool_calls.labels(tool="semantic_get_data_dictionary", status="success").inc()
    mc.tool_duration.labels(tool="semantic_get_data_dictionary").observe(time.monotonic() - start_time)
    return json.dumps(dictionary, indent=2, default=str)
