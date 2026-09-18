"""
Data Import Tools - CSV/Excel file import into database tables.

Provides MCP tools for importing data from uploaded files (CSV, Excel)
into database tables with column mapping support. Supports PostgreSQL,
MariaDB/MySQL, and Microsoft SQL Server.

MCP Tools Provided:
    - list_db_connections: List configured database connections
    - list_database_tables: List tables in a database
    - get_table_columns: Get column metadata for a table
    - batch_insert_rows: Insert rows into a table with column mapping
"""

import json
import logging
import os
from typing import Optional
from fastmcp import FastMCP
from .dml import _error_response, _success_response

logger = logging.getLogger(__name__)


def tool_list_db_connections() -> str:
    """
    MCP Tool: list_db_connections - List all configured database connections.

    Reads the databases.json configuration file and returns a list of
    available database connections with their basic connection details.
    Passwords are excluded from the response for security.

    Returns:
        JSON string containing an array of database connection objects:
        - id: Database ID (config key)
        - name: Human-readable identifier
        - db_type: Database type (postgres, mariadb, mysql, mssql)
        - host: Database host address
        - port: Database port number
        - dbname: Database name

    Example:
        result = await tool_list_db_connections()
        # Returns: [{"id": "my_mariadb", "name": "my_mariadb", ...}, ...]
    """
    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'databases.json')

    try:
        if not os.path.exists(config_path):
            return json.dumps([])

        with open(config_path, 'r') as f:
            configs = json.load(f)

        connections = []
        for db_id, config in configs.items():
            connections.append({
                "id": db_id,
                "name": db_id,
                "db_type": config.get("db_type", "unknown"),
                "host": config.get("host", ""),
                "port": config.get("port", 5432),
                "dbname": config.get("dbname", ""),
            })

        return json.dumps(connections)

    except Exception as e:
        logger.error(f"Error listing database connections: {e}")
        return json.dumps([])


def tool_list_database_tables(
    db_id: str,
    schema: Optional[str] = None,
) -> str:
    """
    MCP Tool: list_database_tables - List tables in a database.

    Connects to the specified database and queries information_schema
    to retrieve a list of all user tables with their schema, column count,
    and row estimate.

    Args:
        db_id: Database ID from databases.json configuration.
        schema: (Optional) Schema name to filter by (PostgreSQL only).

    Returns:
        JSON string containing an array of table objects:
        - name: Table name
        - schema: Schema name
        - table_rows: Estimated row count
        - column_count: Number of columns

    Example:
        result = await tool_list_database_tables("my_mariadb")
        # Returns: [{"name": "users", "schema": "public", ...}, ...]
    """
    try:
        strategy = _resolve_strategy(
            db_id=None,
            db_type=None,
            host=None,
            user=None,
            password=None,
            dbname=None,
            port=None,
        )

        # We need to get strategy from db_id directly
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'databases.json')
        with open(config_path, 'r') as f:
            all_configs = json.load(f)

        if db_id not in all_configs:
            return _error_response(f"Database '{db_id}' not found in configuration", 404)

        db_config = all_configs[db_id]
        strategy_type = db_config.get("db_type", "postgres").lower()

        strategy_map = {
            'postgres': _get_strategy_class('postgres'),
            'mariadb': _get_strategy_class('mariadb'),
            'mysql': _get_strategy_class('mariadb'),
            'mssql': _get_strategy_class('mssql'),
        }

        strategy_class = strategy_map.get(strategy_type)
        if not strategy_class:
            return _error_response(f"Unsupported database type: {strategy_type}", 400)

        conn_details = {
            'host': db_config['host'],
            'user': db_config['user'],
            'password': db_config['password'],
            'dbname': db_config['database'] if 'database' in db_config else db_config.get('dbname', ''),
            'port': db_config.get('port', 5432 if strategy_type == 'postgres' else (3306 if strategy_type in ('mariadb', 'mysql') else 1433)),
        }

        strategy = strategy_class(conn_details)

        with strategy as db_context:
            tables = db_context.get_tables_list(schema=schema)

        return json.dumps(tables)

    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        return _error_response(f"Failed to list tables: {e}", 500)


def tool_get_table_columns(
    db_id: str,
    table_name: str,
    schema: Optional[str] = None,
) -> str:
    """
    MCP Tool: get_table_columns - Get column metadata for a table.

    Connects to the specified database and retrieves detailed column
    information including data type, nullable, max length, and primary
    key status for all columns in the target table.

    Args:
        db_id: Database ID from databases.json configuration.
        table_name: Name of the table to get columns for.
        schema: (Optional) Schema name (PostgreSQL).

    Returns:
        JSON string containing an array of column objects:
        - name: Column name
        - type: SQL data type (e.g., "VARCHAR", "INTEGER")
        - nullable: Whether the column allows NULL values
        - is_primary_key: Whether this is part of the primary key
        - max_length: Maximum length for string types (null if not applicable)

    Example:
        result = await tool_get_table_columns("my_mariadb", "users")
        # Returns: [{"name": "id", "type": "INT", "nullable": false, "is_primary_key": true}, ...]
    """
    try:
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'databases.json')
        with open(config_path, 'r') as f:
            all_configs = json.load(f)

        if db_id not in all_configs:
            return _error_response(f"Database '{db_id}' not found in configuration", 404)

        db_config = all_configs[db_id]
        strategy_type = db_config.get("db_type", "postgres").lower()

        strategy_map = {
            'postgres': _get_strategy_class('postgres'),
            'mariadb': _get_strategy_class('mariadb'),
            'mysql': _get_strategy_class('mariadb'),
            'mssql': _get_strategy_class('mssql'),
        }

        strategy_class = strategy_map.get(strategy_type)
        if not strategy_class:
            return _error_response(f"Unsupported database type: {strategy_type}", 400)

        conn_details = {
            'host': db_config['host'],
            'user': db_config['user'],
            'password': db_config['password'],
            'dbname': db_config['database'] if 'database' in db_config else db_config.get('dbname', ''),
            'port': db_config.get('port', 5432 if strategy_type == 'postgres' else (3306 if strategy_type in ('mariadb', 'mysql') else 1433)),
        }

        strategy = strategy_class(conn_details)

        with strategy as db_context:
            columns = db_context.get_table_columns(table_name, schema=schema)

        return json.dumps(columns)

    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception as e:
        logger.error(f"Error getting table columns: {e}")
        return _error_response(f"Failed to get table columns: {e}", 500)


def tool_batch_insert_rows(
    db_id: str,
    table_name: str,
    columns: list[str],
    rows: list[list],
    batch_size: int = 50,
    schema: Optional[str] = None,
) -> str:
    """
    MCP Tool: batch_insert_rows - Insert rows into a database table.

    Inserts data rows into the specified table using parameterized queries.
    Supports batching to manage payload size. Empty values are converted
    to NULL. Rows are inserted in batches of the specified size.

    Args:
        db_id: Database ID from databases.json configuration.
        table_name: Target table name to insert into.
        columns: List of column names in order matching the row data.
        rows: List of rows, where each row is a list of values.
        batch_size: Number of rows per INSERT statement (default: 50, recommended max: 200).
        schema: (Optional) Schema name (PostgreSQL).

    Returns:
        JSON string containing:
        - success: True if at least some rows were inserted
        - total_rows: Total number of rows attempted
        - inserted_rows: Successfully inserted row count
        - failed_rows: Number of rows that failed to insert
        - batches: Summary of each batch (batch_number, rows, success, error)
        - errors: List of error messages for failed rows

    Example:
        result = await tool_batch_insert_rows(
            db_id="my_mariadb",
            table_name="users",
            columns=["name", "email", "age"],
            rows=[["Alice", "alice@example.com", 30], ["Bob", "bob@example.com", 25]],
            batch_size=50
        )
        # Returns: {"success": true, "total_rows": 2, "inserted_rows": 2, ...}
    """
    if not columns:
        return _error_response("No columns specified", 400)

    if not rows:
        return _error_response("No rows to insert", 400)

    if batch_size < 1:
        return _error_response("batch_size must be at least 1", 400)

    try:
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'databases.json')
        with open(config_path, 'r') as f:
            all_configs = json.load(f)

        if db_id not in all_configs:
            return _error_response(f"Database '{db_id}' not found in configuration", 404)

        db_config = all_configs[db_id]
        strategy_type = db_config.get("db_type", "postgres").lower()

        strategy_map = {
            'postgres': _get_strategy_class('postgres'),
            'mariadb': _get_strategy_class('mariadb'),
            'mysql': _get_strategy_class('mariadb'),
            'mssql': _get_strategy_class('mssql'),
        }

        strategy_class = strategy_map.get(strategy_type)
        if not strategy_class:
            return _error_response(f"Unsupported database type: {strategy_type}", 400)

        conn_details = {
            'host': db_config['host'],
            'user': db_config['user'],
            'password': db_config['password'],
            'dbname': db_config['database'] if 'database' in db_config else db_config.get('dbname', ''),
            'port': db_config.get('port', 5432 if strategy_type == 'postgres' else (3306 if strategy_type in ('mariadb', 'mysql') else 1433)),
        }

        strategy = strategy_class(conn_details)
        total_rows = len(rows)
        inserted_rows = 0
        failed_rows = 0
        batch_results = []
        all_errors = []

        with strategy as db_context:
            for batch_start in range(0, total_rows, batch_size):
                batch_end = min(batch_start + batch_size, total_rows)
                batch_rows = rows[batch_start:batch_end]
                batch_number = (batch_start // batch_size) + 1

                try:
                    count = db_context.batch_insert(table_name, columns, batch_rows, schema=schema)
                    inserted_rows += count
                    batch_results.append({
                        "batch_number": batch_number,
                        "start_row": batch_start + 1,
                        "end_row": batch_end,
                        "rows": len(batch_rows),
                        "success": True,
                        "error": None,
                    })
                except Exception as batch_error:
                    error_msg = str(batch_error)
                    failed_rows += len(batch_rows)
                    batch_results.append({
                        "batch_number": batch_number,
                        "start_row": batch_start + 1,
                        "end_row": batch_end,
                        "rows": len(batch_rows),
                        "success": False,
                        "error": error_msg,
                    })
                    all_errors.append(f"Batch {batch_number}: {error_msg}")

        return json.dumps({
            "success": inserted_rows > 0,
            "total_rows": total_rows,
            "inserted_rows": inserted_rows,
            "failed_rows": failed_rows,
            "batches": batch_results,
            "errors": all_errors if all_errors else None,
        })

    except ValueError as e:
        return _error_response(str(e), 400)
    except Exception as e:
        logger.error(f"Error during batch insert: {e}")
        return _error_response(f"Failed to insert rows: {e}", 500)


def _get_strategy_class(db_type: str):
    """Get the strategy class for a database type."""
    from .postgres import PostgresStrategy
    from .mariadb import MariaDBStrategy
    from .mssql import MSSQLStrategy

    strategy_map = {
        'postgres': PostgresStrategy,
        'mariadb': MariaDBStrategy,
        'mysql': MariaDBStrategy,
        'mssql': MSSQLStrategy,
    }
    cls = strategy_map.get(db_type)
    if not cls:
        raise ValueError(f"Unsupported database type: {db_type}")
    return cls


def _error_response(message: str, status_code: int) -> str:
    """Return a standardized error JSON response."""
    return json.dumps({
        "success": False,
        "error": message,
        "status_code": status_code,
    })


def register_import_tools(mcp: FastMCP, db_manager=None):
    """
    Register the data import MCP tools with the FastMCP server.

    Args:
        mcp: The FastMCP server instance to register tools on.
        db_manager: The DbManager instance for database configuration.
    """
    @mcp.tool(name="list_db_connections")
    def list_db_connections_wrapper() -> str:
        """List all configured database connections from databases.json."""
        return tool_list_db_connections()

    @mcp.tool(name="list_database_tables")
    def list_database_tables_wrapper(db_id: str, schema: Optional[str] = None) -> str:
        """List all tables in the specified database connection."""
        return tool_list_database_tables(db_id=db_id, schema=schema)

    @mcp.tool(name="get_table_columns")
    def get_table_columns_wrapper(db_id: str, table_name: str, schema: Optional[str] = None) -> str:
        """Get column metadata for a table in the specified database."""
        return tool_get_table_columns(db_id=db_id, table_name=table_name, schema=schema)

    @mcp.tool(name="batch_insert_rows")
    def batch_insert_rows_wrapper(
        db_id: str,
        table_name: str,
        columns: list[str],
        rows: list[list],
        batch_size: int = 50,
        schema: Optional[str] = None,
    ) -> str:
        """Insert rows into a table with column mapping. batch_size recommended max: 200."""
        return tool_batch_insert_rows(
            db_id=db_id,
            table_name=table_name,
            columns=columns,
            rows=rows,
            batch_size=batch_size,
            schema=schema,
        )
