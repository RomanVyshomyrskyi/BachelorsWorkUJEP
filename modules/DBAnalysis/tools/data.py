import json
import re
from typing import Literal
from ..models.connection import ConnectionDetails
from ..strategies.factory import get_db_strategy
from modules.log_utils import LogCollector

_IDENTIFIER_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$')

def _validate_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid table name: '{name}'")
    return name

def _default_port(db_type: str) -> int:
    return {"postgres": 5432, "mariadb": 3306, "mysql": 3306, "mssql": 1433}.get(db_type, 5432)

def tool_run_sql(
    db_type: Literal["postgres", "mariadb", "mysql", "mssql"],
    host: str,
    user: str,
    password: str,
    dbname: str,
    query: str,
    port: int = 0
) -> str:
    """
    Executes a read-only SQL query (SELECT) against the database.
    Returns data in JSON format.
    """
    log = LogCollector(f"{__name__}.run_sql")
    if not port:
        port = _default_port(db_type)
    try:
        log.info(f"Executing query on {db_type}://{host}:{port}/{dbname}")
        conn_details = ConnectionDetails(
            host=host, user=user, password=password, dbname=dbname, port=port
        )
        
        strategy = get_db_strategy(db_type, conn_details.model_dump())

        with strategy as db_context:
            log.info(f"Query: {query[:200]}{'...' if len(query) > 200 else ''}")
            results = db_context.execute_query(query)

        log.info(f"Query returned {len(results)} rows")
        return log.collect(json.dumps(results, default=str))

    except Exception as e:
        log.error(f"Query execution error on {dbname}: {e}")
        return f"Query Execution Error: {e}"

def tool_get_table_data(
    db_type: Literal["postgres", "mariadb", "mysql", "mssql"],
    host: str,
    user: str,
    password: str,
    dbname: str,
    table_name: str,
    limit: int = 100,
    port: int = 0
) -> str:
    """
    Fetches the first N rows from a specific table.
    """
    log = LogCollector(f"{__name__}.get_table_data")
    if not port:
        port = _default_port(db_type)
    try:
        _validate_identifier(table_name)
        log.info(f"Fetching {limit} rows from {db_type}://{host}:{port}/{dbname}.{table_name}")
        conn_details = ConnectionDetails(
            host=host, user=user, password=password, dbname=dbname, port=port
        )
        
        strategy = get_db_strategy(db_type, conn_details.model_dump())

        if db_type == "mssql":
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

def register_data_tools(mcp):
    mcp.tool(name="run_read_only_sql")(tool_run_sql)
    mcp.tool(name="get_table_data")(tool_get_table_data)