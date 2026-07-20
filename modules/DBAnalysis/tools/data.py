import json
 import re
 import threading
 import time
 from typing import Optional
 from ..models.connection import ConnectionDetails
 from ..strategies.factory import get_db_strategy
 from ..db_manager import DbManager
 from ..strategies.base import MAX_ROWS
 from modules.log_utils import LogCollector
 from modules.metrics import get_metrics

_IDENTIFIER_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$')

# Maximum rows for table preview
MAX_TABLE_PREVIEW = 100

# Maximum rows for raw SQL queries
MAX_SQL_ROWS = 1000


def _validate_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError("Invalid table name format")
    return name


def _sanitize_error(e: Exception) -> str:
    """Return a generic error message to the caller, log details server-side."""
    logger = LogCollector(f"data.error").error
    logger(f"Internal error: {e}")
    return "An error occurred while processing your request. Please try again."


def _resolve_config(
    db_manager: Optional[DbManager],
    db_id: Optional[str],
    db_type: Optional[str],
    host: Optional[str],
    user: Optional[str],
    password: Optional[str],
    dbname: Optional[str],
    port: Optional[int],
) -> dict:
    if db_id:
        if db_manager is None:
            raise ValueError("db_id provided but no database manager available")
        cfg = db_manager.get_config(db_id)
        if not cfg:
            raise ValueError(f"Database '{db_id}' not found in configuration")
        return cfg
    if not db_type or not host or not user or not dbname:
        raise ValueError("Either db_id or all of db_type, host, user, dbname must be provided")
    return {
        "db_type": db_type,
        "host": host,
        "port": port or _default_port(db_type),
        "dbname": dbname,
        "user": user,
        "password": password or "",
    }


def _default_port(db_type: str) -> int:
    return {"postgres": 5432, "mariadb": 3306, "mysql": 3306, "mssql": 1433}.get(db_type, 5432)


def tool_run_sql(
    db_manager: Optional[DbManager],
    query: str,
    db_id: Optional[str] = None,
    db_type: Optional[str] = None,
    host: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
    port: Optional[int] = None,
    max_rows: int = MAX_SQL_ROWS,
) -> str:
    log = LogCollector(f"{__name__}.run_sql")
    try:
        cfg = _resolve_config(db_manager, db_id, db_type, host, user, password, dbname, port)
    except ValueError as e:
        return str(e)

    if not query or not query.strip():
        return "Query cannot be empty"

    # Sanitize query length for logging
    log.info(f"Executing query on {cfg['db_type']}://{cfg['host']}:{cfg['port']}/{cfg['dbname']}")
    conn_details = ConnectionDetails(**cfg)
    strategy = get_db_strategy(cfg['db_type'], conn_details.model_dump())

    try:
        with strategy as db_context:
            log.info(f"Query: {query[:200]}{'...' if len(query) > 200 else ''}")
            results = db_context.execute_query(query, max_rows=max_rows)

        log.info(f"Query returned {len(results)} rows")
        return log.collect(json.dumps(results, default=str))

    except TimeoutError as e:
        log.error(f"Query timed out on {cfg.get('dbname', db_id or '?')}")
        return str(e)
    except RuntimeError as e:
        return _sanitize_error(e)
    except Exception as e:
        log.error(f"Unexpected error on {cfg.get('dbname', db_id or '?')}: {e}")
        return _sanitize_error(e)


def tool_get_table_data(
    db_manager: Optional[DbManager],
    table_name: str,
    db_id: Optional[str] = None,
    db_type: Optional[str] = None,
    host: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
    limit: int = MAX_TABLE_PREVIEW,
    port: Optional[int] = None,
) -> str:
    log = LogCollector(f"{__name__}.get_table_data")

    # Clamp limit to prevent abuse
    if limit < 1:
        limit = MAX_TABLE_PREVIEW
    if limit > MAX_TABLE_PREVIEW:
        limit = MAX_TABLE_PREVIEW

    try:
        _validate_identifier(table_name)
    except ValueError as e:
        return str(e)

    try:
        cfg = _resolve_config(db_manager, db_id, db_type, host, user, password, dbname, port)
    except ValueError as e:
        return str(e)

    log.info(f"Fetching {limit} rows from {cfg['db_type']}://{cfg['host']}:{cfg['port']}/{cfg['dbname']}.{table_name}")
    conn_details = ConnectionDetails(**cfg)
    strategy = get_db_strategy(cfg['db_type'], conn_details.model_dump())

    try:
        if cfg['db_type'] == "mssql":
            query = f"SELECT TOP {limit} * FROM {table_name}"
        else:
            query = f"SELECT * FROM {table_name} LIMIT {limit}"

        with strategy as db_context:
            results = db_context.execute_query(query, max_rows=limit)

        log.info(f"Retrieved {len(results)} rows from {table_name}")
        return json.dumps(results, default=str)

    except TimeoutError as e:
        return str(e)
    except RuntimeError as e:
        return _sanitize_error(e)
    except Exception as e:
        log.error(f"Data retrieval error for {table_name}: {e}")
        return _sanitize_error(e)


def register_data_tools(mcp, db_manager=None):
@mcp.tool(name="run_read_only_sql")
     def run_read_only_sql(
         query: str,
         db_id: Optional[str] = None,
         db_type: Optional[str] = None,
         host: Optional[str] = None,
         user: Optional[str] = None,
         password: Optional[str] = None,
         dbname: Optional[str] = None,
         port: Optional[int] = None,
     ) -> str:
         mc = get_metrics()
         start = time.monotonic()
         try:
             result = tool_run_sql(db_manager, query, db_id, db_type, host, user, password, dbname, port)
             mc.queries_executed.labels(source="db_analysis_sql").inc()
             mc.tool_calls.labels(tool="db_analysis_run_sql", status="success").inc()
             mc.tool_duration.labels(tool="db_analysis_run_sql").observe(time.monotonic() - start)
             return result
         except Exception as e:
             mc.tool_calls.labels(tool="db_analysis_run_sql", status="error").inc()
             mc.record_error(tool="db_analysis_run_sql", error_message=str(e))
             raise

     @mcp.tool(name="get_table_data")
     def get_table_data(
         table_name: str,
         db_id: Optional[str] = None,
         db_type: Optional[str] = None,
         host: Optional[str] = None,
         user: Optional[str] = None,
         password: Optional[str] = None,
         dbname: Optional[str] = None,
         limit: int = MAX_TABLE_PREVIEW,
         port: Optional[int] = None,
     ) -> str:
         mc = get_metrics()
         start = time.monotonic()
         try:
             result = tool_get_table_data(db_manager, table_name, db_id, db_type, host, user, password, dbname, limit, port)
             mc.queries_executed.labels(source="db_analysis_table").inc()
             mc.tool_calls.labels(tool="db_analysis_get_table_data", status="success").inc()
             mc.tool_duration.labels(tool="db_analysis_get_table_data").observe(time.monotonic() - start)
             mc.db_queries.labels(db_type=db_type or "unknown", status="success").inc()
             return result
         except Exception as e:
             mc.tool_calls.labels(tool="db_analysis_get_table_data", status="error").inc()
             mc.record_error(tool="db_analysis_get_table_data", error_message=str(e))
             raise
