import json
import re
from typing import Optional
from ..models.connection import ConnectionDetails
from ..strategies.factory import get_db_strategy
from ..db_manager import DbManager
from modules.log_utils import LogCollector

_IDENTIFIER_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$')

def _validate_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid table name: '{name}'")
    return name


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
) -> str:
    log = LogCollector(f"{__name__}.run_sql")
    try:
        cfg = _resolve_config(db_manager, db_id, db_type, host, user, password, dbname, port)
    except ValueError as e:
        return str(e)
    try:
        log.info(f"Executing query on {cfg['db_type']}://{cfg['host']}:{cfg['port']}/{cfg['dbname']}")
        conn_details = ConnectionDetails(**cfg)
        strategy = get_db_strategy(cfg['db_type'], conn_details.model_dump())

        with strategy as db_context:
            log.info(f"Query: {query[:200]}{'...' if len(query) > 200 else ''}")
            results = db_context.execute_query(query)

        log.info(f"Query returned {len(results)} rows")
        return log.collect(json.dumps(results, default=str))

    except Exception as e:
        log.error(f"Query execution error on {cfg.get('dbname', db_id or '?')}: {e}")
        return f"Query Execution Error: {e}"


def tool_get_table_data(
    db_manager: Optional[DbManager],
    table_name: str,
    db_id: Optional[str] = None,
    db_type: Optional[str] = None,
    host: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
    limit: int = 100,
    port: Optional[int] = None,
) -> str:
    log = LogCollector(f"{__name__}.get_table_data")
    try:
        _validate_identifier(table_name)
    except ValueError as e:
        return str(e)
    try:
        cfg = _resolve_config(db_manager, db_id, db_type, host, user, password, dbname, port)
    except ValueError as e:
        return str(e)
    try:
        log.info(f"Fetching {limit} rows from {cfg['db_type']}://{cfg['host']}:{cfg['port']}/{cfg['dbname']}.{table_name}")
        conn_details = ConnectionDetails(**cfg)
        strategy = get_db_strategy(cfg['db_type'], conn_details.model_dump())

        if cfg['db_type'] == "mssql":
            query = f"SELECT TOP {limit} * FROM {table_name}"
        else:
            query = f"SELECT * FROM {table_name} LIMIT {limit}"

        with strategy as db_context:
            results = db_context.execute_query(query)

        log.info(f"Retrieved {len(results)} rows from {table_name}")
        return json.dumps(results, default=str)

    except Exception as e:
        log.error(f"Data retrieval error for {table_name}: {e}")
        return f"Data Retrieval Error: {e}"


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
        return tool_run_sql(db_manager, query, db_id, db_type, host, user, password, dbname, port)

    @mcp.tool(name="get_table_data")
    def get_table_data(
        table_name: str,
        db_id: Optional[str] = None,
        db_type: Optional[str] = None,
        host: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        dbname: Optional[str] = None,
        limit: int = 100,
        port: Optional[int] = None,
    ) -> str:
        return tool_get_table_data(db_manager, table_name, db_id, db_type, host, user, password, dbname, limit, port)
