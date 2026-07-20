import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from modules.SupersetModule.tools.sqllab import sqllab_execute_query, sqllab_get_query_results
from modules.SupersetModule.tools.datasets import get_database_schema as _get_schema
from modules.metrics import get_metrics

logger = logging.getLogger(__name__)

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
    return [c["column_name"] for c in columns if _classify_column(c["data_type"]) == "numeric"]


def _extract_text(columns: List[Dict[str, Any]]) -> List[str]:
    return [c["column_name"] for c in columns if _classify_column(c["data_type"]) == "text"]


def _extract_date(columns: List[Dict[str, Any]]) -> List[str]:
    return [c["column_name"] for c in columns if _classify_column(c["data_type"]) == "date"]


def _quote(col: str) -> str:
    return f'"{col}"'


def _escape(val: str) -> str:
    return val.replace("'", "''")


def _build_numeric_sql(schema: str, table: str, columns: List[str]) -> str:
    start_time = time.monotonic()
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
    start_time = time.monotonic()
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
    start_time = time.monotonic()
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


async def _run_sql_and_get_data(
    manager, server_id, database_id, sql: str, schema: Optional[str] = None
) -> Tuple[bool, Any]:
    try:
        exec_raw = await sqllab_execute_query(
            manager, server_id, database_id, sql, schema=schema
        )
        exec_data = json.loads(exec_raw)
        client_id = exec_data.get("result", {}).get("query", {}).get("client_id")
        if not client_id:
            return False, f"No client_id from execution: {exec_data}"
        import asyncio
        await asyncio.sleep(1.5)
        results_raw = await sqllab_get_query_results(manager, server_id, client_id)
        results = json.loads(results_raw)
        rows = results.get("data", [])
        return True, rows
    except Exception as e:
        logger.warning(f"SQL profiling query failed: {e}")
        return False, str(e)


async def _run_row_count(
    manager, server_id, database_id, schema: str, table: str
) -> Optional[int]:
    sql = f"SELECT COUNT(*) AS row_count FROM {_quote(schema)}.{_quote(table)}"
    ok, data = await _run_sql_and_get_data(manager, server_id, database_id, sql, schema)
    if ok and data:
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
    start_time = time.monotonic()
    if not columns:
        schema_raw = await _get_schema(manager, server_id, database_id, schema)
        try:
            schema_data = json.loads(schema_raw)
        except (json.JSONDecodeError, TypeError):
            return schema_raw if isinstance(schema_raw, str) else json.dumps({"error": True, "message": str(schema_raw)})
        tables = schema_data.get("tables", [])
        match = [t for t in tables if t.get("table_name", "").lower() == table.lower()]
        if not match:
            return json.dumps({"error": True, "message": f"Table '{table}' not found in schema '{schema}'"})
        columns = match[0].get("columns", [])

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

    if numeric_cols:
        sql = _build_numeric_sql(schema, table, numeric_cols)
        ok, data = await _run_sql_and_get_data(manager, server_id, database_id, sql, schema)
        if ok:
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

    if text_cols:
        sql = _build_text_sql(schema, table, text_cols)
        ok, data = await _run_sql_and_get_data(manager, server_id, database_id, sql, schema)
        if ok:
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

    if date_cols:
        sql = _build_date_sql(schema, table, date_cols)
        ok, data = await _run_sql_and_get_data(manager, server_id, database_id, sql, schema)
        if ok:
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


def _is_metric_candidate(col: Dict[str, Any]) -> bool:
    return _classify_column(col["data_type"]) == "numeric"


def _is_dimension_candidate(col: Dict[str, Any]) -> bool:
    cat = _classify_column(col["data_type"])
    return cat in ("text", "boolean", "date") or cat == "other"


async def suggest_metrics(
    manager,
    server_id: str,
    database_id: int,
    schema: str,
    table: str,
) -> str:
    start_time = time.monotonic()
    schema_raw = await _get_schema(manager, server_id, database_id, schema)
    try:
        schema_data = json.loads(schema_raw)
    except (json.JSONDecodeError, TypeError):
        return schema_raw if isinstance(schema_raw, str) else json.dumps({"error": True, "message": str(schema_raw)})
    tables = schema_data.get("tables", [])
    match = [t for t in tables if t.get("table_name", "").lower() == table.lower()]
    if not match:
        return json.dumps({"error": True, "message": f"Table '{table}' not found"})
    columns = match[0].get("columns", [])

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
    start_time = time.monotonic()
    schema_raw = await _get_schema(manager, server_id, database_id, schema)
    try:
        schema_data = json.loads(schema_raw)
    except (json.JSONDecodeError, TypeError):
        return schema_raw if isinstance(schema_raw, str) else json.dumps({"error": True, "message": str(schema_raw)})
    tables = schema_data.get("tables", [])
    match = [t for t in tables if t.get("table_name", "").lower() == table.lower()]
    if not match:
        return json.dumps({"error": True, "message": f"Table '{table}' not found"})
    columns = match[0].get("columns", [])

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


async def get_data_dictionary(
    manager,
    server_id: str,
    database_id: int,
    schema: str,
    table: str,
    include_statistics: bool = True,
) -> str:
    start_time = time.monotonic()
    schema_raw = await _get_schema(manager, server_id, database_id, schema)
    try:
        schema_data = json.loads(schema_raw)
    except (json.JSONDecodeError, TypeError):
        return schema_raw if isinstance(schema_raw, str) else json.dumps({"error": True, "message": str(schema_raw)})
    tables = schema_data.get("tables", [])
    match = [t for t in tables if t.get("table_name", "").lower() == table.lower()]
    if not match:
        return json.dumps({"error": True, "message": f"Table '{table}' not found"})
    columns = match[0].get("columns", [])

    profile = {}
    if include_statistics:
        profile_raw = await profile_table(manager, server_id, database_id, schema, table, columns=columns)
        try:
            profile = json.loads(profile_raw)
        except (json.JSONDecodeError, TypeError):
            pass

    dictionary = {
        "table": table,
        "schema": schema,
        "database_id": database_id,
        "row_count": profile.get("row_count") if include_statistics else None,
        "columns": [],
    }

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
