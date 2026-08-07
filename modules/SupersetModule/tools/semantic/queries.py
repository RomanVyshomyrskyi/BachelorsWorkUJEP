"""
SQL query builder functions for semantic profiling.

Contains functions that generate SQL queries for profiling numeric,
text, date columns and finding top values.
"""

from typing import Any, Dict, List

from modules.SupersetModule.tools.semantic.helpers import _escape, _quote


def _build_numeric_sql(schema: str, table: str, columns: List[str]) -> str:
    """
    Build a SQL query that generates statistics for numeric columns.

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
        q = _quote(col)
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
    return "\nUNION ALL\n".join(unions)


def _build_text_sql(schema: str, table: str, columns: List[str]) -> str:
    """
    Build a SQL query that generates statistics for text columns.

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
    return "\nUNION ALL\n".join(unions)


def _build_date_sql(schema: str, table: str, columns: List[str]) -> str:
    """
    Build a SQL query that generates statistics for date/time columns.

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
    return "\nUNION ALL\n".join(unions)


def _build_top_values_sql(schema: str, table: str, column: str, limit: int = 10) -> str:
    """
    Build a SQL query to find the most frequent values in a column.

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
