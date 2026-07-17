import json
import re
from typing import Literal
from ..models.connection import ConnectionDetails
from ..strategies.factory import get_db_strategy

_IDENTIFIER_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$')

def _validate_identifier(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid table name: '{name}'")
    return name

def tool_run_sql(
    db_type: Literal["postgres", "mariadb", "mysql", "mssql"],
    host: str,
    user: str,
    password: str,
    dbname: str,
    query: str,
    port: int = 5432
) -> str:
    """
    Executes a read-only SQL query (SELECT) against the database.
    Returns data in JSON format.
    """
    try:
        conn_details = ConnectionDetails(
            host=host, user=user, password=password, dbname=dbname, port=port
        )
        
        strategy = get_db_strategy(db_type, conn_details.model_dump())

        with strategy as db_context:
            results = db_context.execute_query(query)

        return json.dumps(results, default=str)

    except Exception as e:
        return f"Query Execution Error: {e}"

def tool_get_table_data(
    db_type: Literal["postgres", "mariadb", "mysql", "mssql"],
    host: str,
    user: str,
    password: str,
    dbname: str,
    table_name: str,
    limit: int = 100,
    port: int = 5432
) -> str:
    """
    Fetches the first N rows from a specific table.
    """
    try:
        _validate_identifier(table_name)
        conn_details = ConnectionDetails(
            host=host, user=user, password=password, dbname=dbname, port=port
        )
        
        strategy = get_db_strategy(db_type, conn_details.model_dump())

        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        # MSSQL uses TOP instead of LIMIT
        if db_type == "mssql":
            query = f"SELECT TOP {limit} * FROM {table_name}"

        with strategy as db_context:
            results = db_context.execute_query(query)

        return json.dumps(results, default=str)

    except Exception as e:
        return f"Data Retrieval Error: {e}"

def register_data_tools(mcp):
    mcp.tool(name="run_read_only_sql")(tool_run_sql)
    mcp.tool(name="get_table_data")(tool_get_table_data)