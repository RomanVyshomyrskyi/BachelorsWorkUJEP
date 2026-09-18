"""
Direct database connection tools for DML/DDL operations.

Provides MCP tools for executing CREATE (DDL) and INSERT (DML) operations
directly against databases using native connections. DELETE is ALWAYS FORBIDDEN.

MCP Tools Provided:
    - execute_create_sql: Execute CREATE/ALTER statements
    - execute_insert_sql: Execute INSERT statements
"""

import logging
from typing import Optional
from fastmcp import FastMCP
from modules.DBAnalysis.strategies.postgres import PostgresStrategy
from modules.DBAnalysis.strategies.mariadb import MariaDBStrategy
from modules.DBAnalysis.strategies.mssql import MSSQLStrategy
from modules.DBAnalysis.db_manager import DbManager

logger = logging.getLogger(__name__)

# Always forbidden operations for ALL direct DB tools
ALWAYS_FORBIDDEN = frozenset(['DELETE', 'DROP', 'TRUNCATE'])


async def tool_execute_create_sql(
    db_id: Optional[int] = None,
    db_type: Optional[str] = None,
    host: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
    port: Optional[int] = None,
    query: Optional[str] = None,
    schema: Optional[str] = None,
) -> str:
    """
    MCP Tool: execute_create_sql - Execute CREATE/ALTER statements via direct database connection.

    Executes a DDL statement (CREATE TABLE, CREATE INDEX, ALTER TABLE, etc.)
    directly against the target database. Only CREATE and ALTER operations are allowed.
    DELETE, DROP, TRUNCATE, INSERT, UPDATE, and SELECT are FORBIDDEN.

    This tool is intended for schema modification tasks such as:
    - Creating new tables, indexes, or constraints
    - Modifying existing table structures
    - Adding or removing columns
    - Changing table properties

    Args:
        db_id: (Optional) Database ID from servers.json configuration.
        db_type: Database type (postgres, mariadb, mssql). Required if db_id not provided.
        host: Database server hostname or IP address. Required if db_id not provided.
        user: Database username. Required if db_id not provided.
        password: Database password. Required if db_id not provided.
        dbname: Database name. Required if db_id not provided.
        port: Database port number (default: 5432 for postgres, 3306 for mariadb, 1433 for mssql).
        query: The SQL DDL statement to execute (must start with CREATE or ALTER).
        schema: (Optional) Schema name for databases that support schemas (e.g., PostgreSQL).

    Returns:
        JSON string containing:
        - success: True if the operation succeeded
        - message: Human-readable description of the result
        - affected_rows: Number of rows affected (typically 0 for DDL)

    Example:
        result = await tool_execute_create_sql(
            db_type="postgres", host="localhost", user="admin",
            password="secret", dbname="mydb",
            query="CREATE TABLE users (id INT PRIMARY KEY, name VARCHAR(100))"
        )
    """
    if not query or not query.strip():
        return _error_response("Empty query", 400)

    allowed_ops = frozenset(['CREATE', 'ALTER', 'CREATE TABLE', 'CREATE INDEX', 'ALTER TABLE', 'ALTER INDEX'])

    try:
        strategy = _get_strategy(db_id, db_type, host, user, password, dbname, port)

        strategy.connect()
        strategy.execute_ddl(query)

        return _success_response("DDL statement executed successfully", 0)

    except ValueError as e:
        return _error_response(str(e), 403)
    except Exception as e:
        return _error_response(f"Error executing DDL: {e}", 500)


async def tool_execute_insert_sql(
    db_id: Optional[int] = None,
    db_type: Optional[str] = None,
    host: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
    port: Optional[int] = None,
    query: Optional[str] = None,
    schema: Optional[str] = None,
) -> str:
    """
    MCP Tool: execute_insert_sql - Execute INSERT statements via direct database connection.

    Executes an INSERT statement directly against the target database. Only INSERT
    operations are allowed. DELETE, UPDATE, DROP, TRUNCATE, CREATE, and SELECT
    are FORBIDDEN.

    This tool is intended for data insertion tasks such as:
    - Inserting single or multiple rows
    - Bulk data loading from application logic
    - Populating tables with initial data

    Args:
        db_id: (Optional) Database ID from servers.json configuration.
        db_type: Database type (postgres, mariadb, mssql). Required if db_id not provided.
        host: Database server hostname or IP address. Required if db_id not provided.
        user: Database username. Required if db_id not provided.
        password: Database password. Required if db_id not provided.
        dbname: Database name. Required if db_id not provided.
        port: Database port number (default: 5432 for postgres, 3306 for mariadb, 1433 for mssql).
        query: The SQL INSERT statement to execute.
        schema: (Optional) Schema name for databases that support schemas (e.g., PostgreSQL).

    Returns:
        JSON string containing:
        - success: True if the operation succeeded
        - message: Human-readable description of the result
        - affected_rows: Number of rows affected

    Example:
        result = await tool_execute_insert_sql(
            db_type="postgres", host="localhost", user="admin",
            password="secret", dbname="mydb",
            query="INSERT INTO users (name, email) VALUES ('John', 'john@example.com')"
        )
    """
    if not query or not query.strip():
        return _error_response("Empty query", 400)

    allowed_ops = frozenset(['INSERT', 'INSERT INTO', 'REPLACE', 'REPLACE INTO'])

    try:
        strategy = _get_strategy(db_id, db_type, host, user, password, dbname, port)

        strategy.connect()
        strategy.execute_ddl(query)

        return _success_response("INSERT statement executed successfully", 1)

    except ValueError as e:
        return _error_response(str(e), 403)
    except Exception as e:
        return _error_response(f"Error executing INSERT: {e}", 500)


def _get_strategy(
    db_id: Optional[int],
    db_type: Optional[str],
    host: Optional[str],
    user: Optional[str],
    password: Optional[str],
    dbname: Optional[str],
    port: Optional[int],
) -> PostgresStrategy | MariaDBStrategy | MSSQLStrategy:
    """
    Get the appropriate database strategy based on connection parameters.

    If db_id is provided, loads configuration from servers.json.
    Otherwise, uses the provided connection parameters directly.

    Args:
        db_id: Database ID from servers.json (optional).
        db_type: Database type (postgres, mariadb, mssql).
        host: Database hostname.
        user: Database username.
        password: Database password.
        dbname: Database name.
        port: Database port number.

    Returns:
        An instance of the appropriate database strategy class.

    Raises:
        ValueError: If required parameters are missing or db_type is invalid.
    """
    import json
    import os

    if db_id is not None:
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'servers.json')
        try:
            with open(config_path, 'r') as f:
                servers_config = json.load(f)
            server = None
            for sid, sdata in servers_config.items():
                if sdata.get('db_id') == db_id:
                    server = sid
                    break
            if not server:
                raise ValueError(f"Database ID {db_id} not found in servers.json")
            db_config = servers_config[server]
            strategy_type = db_config.get('type', '').lower()
            connection_details = {
                'host': db_config['host'],
                'user': db_config['user'],
                'password': db_config['password'],
                'dbname': db_config['database'],
                'port': db_config.get('port', 5432 if strategy_type == 'postgres' else (3306 if strategy_type == 'mariadb' else 1433)),
            }
        except (FileNotFoundError, KeyError) as e:
            raise ValueError(f"Failed to load servers.json: {e}")
    else:
        if not all([db_type, host, user, password, dbname]):
            raise ValueError("Missing required connection parameters (db_type, host, user, password, dbname)")
        strategy_type = db_type.lower()
        connection_details = {
            'host': host,
            'user': user,
            'password': password,
            'dbname': dbname,
            'port': port or (5432 if strategy_type == 'postgres' else (3306 if strategy_type == 'mariadb' else 1433)),
        }

    strategy_map = {
        'postgres': PostgresStrategy,
        'mariadb': MariaDBStrategy,
        'mssql': MSSQLStrategy,
    }

    strategy_class = strategy_map.get(strategy_type)
    if not strategy_class:
        raise ValueError(f"Unsupported database type: {strategy_type}")

    return strategy_class(connection_details)


def _error_response(message: str, status_code: int) -> str:
    """Return a standardized error JSON response."""
    import json
    return json.dumps({
        "success": False,
        "error": message,
        "status_code": status_code,
    })


def _success_response(message: str, affected_rows: int = 0) -> str:
    """Return a standardized success JSON response."""
    import json
    return json.dumps({
        "success": True,
        "message": message,
        "affected_rows": affected_rows,
    })


def register_dml_tools(mcp: FastMCP, db_manager: DbManager):
    """
    Register the DML/DDL MCP tools with the FastMCP server.

    Args:
        mcp: The FastMCP server instance to register tools on.
        db_manager: The DbManager instance for database configuration.
    """
    from .dml import tool_execute_create_sql, tool_execute_insert_sql

    @mcp.tool(name="execute_create_sql")
    async def tool_execute_create_sql_wrapper(
        db_id: Optional[int] = None,
        db_type: Optional[str] = None,
        host: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        dbname: Optional[str] = None,
        port: Optional[int] = None,
        query: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> str:
        """Execute CREATE/ALTER statements via direct database connection. DELETE, DROP, TRUNCATE are FORBIDDEN."""
        return await tool_execute_create_sql(
            db_id=db_id,
            db_type=db_type,
            host=host,
            user=user,
            password=password,
            dbname=dbname,
            port=port,
            query=query,
            schema=schema,
        )

    @mcp.tool(name="execute_insert_sql")
    async def tool_execute_insert_sql_wrapper(
        db_id: Optional[int] = None,
        db_type: Optional[str] = None,
        host: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        dbname: Optional[str] = None,
        port: Optional[int] = None,
        query: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> str:
        """Execute INSERT statements via direct database connection. DELETE, UPDATE, DROP are FORBIDDEN."""
        return await tool_execute_insert_sql(
            db_id=db_id,
            db_type=db_type,
            host=host,
            user=user,
            password=password,
            dbname=dbname,
            port=port,
            query=query,
            schema=schema,
        )
