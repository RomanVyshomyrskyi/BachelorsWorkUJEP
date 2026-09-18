"""
DML execution tools for Superset SQL Lab.

Provides MCP tools for executing SELECT, INSERT, and UPDATE queries
via Superset's SQL Lab API. DELETE is ALWAYS FORBIDDEN.

MCP Tools Provided:
    - superset_execute_sql_query: Execute SELECT/WITH/SHOW queries
    - superset_execute_sql_insert: Execute INSERT statements
    - superset_execute_sql_update: Execute UPDATE statements
"""

import json
import time
from typing import Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.sql_lab.execute import sqllab_execute_query
from modules.SupersetModule.tools.sql_lab.query_validation import (
    validate_select_query,
    validate_insert_query,
    validate_update_query,
    validate_dml_query,
)
from modules.SupersetModule.exceptions import SqlLabError
from modules.metrics import get_metrics


async def execute_sql_query(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    sql_query: str,
    schema: Optional[str] = None,
) -> str:
    """
    MCP Tool: superset_execute_sql_query - Execute SELECT/WITH/SHOW queries via Superset SQL Lab.

    Sends a SQL query to Superset's SQL Lab engine for execution. Only SELECT-type
    statements are allowed. DELETE, INSERT, UPDATE, DROP, CREATE, and all DDL/DML
    operations are FORBIDDEN.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        database_id: The numeric ID of the database to execute the query against.
        sql_query: The SQL SELECT query string to execute.
        schema: Optional schema name for databases that support schemas (e.g., PostgreSQL).

    Returns:
        JSON string containing the query results, metadata (column names, row count),
        and execution details. Returns SqlLabError JSON on failure.

    Examples:
        result = await execute_sql_query(
            manager, server_id="main", database_id=1,
            sql_query="SELECT * FROM users WHERE active = true"
        )
        # Returns JSON with query results and metadata
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_execute_sql_query", status="error").inc()
        mc.record_error(tool="superset_execute_sql_query", error_message=f"Server '{server_id}' not found.")
        return SqlLabError(f"Server '{server_id}' not found.", status_code=404).to_json()

    start_time = time.monotonic()
    try:
        validate_select_query(sql_query)
        validate_dml_query(sql_query, 'superset_execute_sql_query')

        result = await sqllab_execute_query(
            manager, server_id, database_id, sql_query, schema
        )

        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_execute_sql_query", status="success").inc()
        mc.tool_duration.labels(tool="superset_execute_sql_query").observe(
            time.monotonic() - start_time
        )
        mc.queries_executed.labels(source="sql_lab_select").inc()
        return result

    except ValueError as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_execute_sql_query", status="error").inc()
        mc.record_error(tool="superset_execute_sql_query", error_message=str(e))
        return SqlLabError(str(e), status_code=403).to_json()
    except Exception as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_execute_sql_query", status="error").inc()
        mc.record_error(tool="superset_execute_sql_query", error_message=str(e))
        return SqlLabError(f"Unexpected error executing SQL: {e}", details=str(e)).to_json()


async def execute_sql_insert(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    sql_query: str,
    schema: Optional[str] = None,
) -> str:
    """
    MCP Tool: superset_execute_sql_insert - Execute INSERT statements via Superset SQL Lab.

    Sends an INSERT query to Superset's SQL Lab engine for execution. Only INSERT
    statements are allowed. DELETE, UPDATE, DROP, CREATE, and all DDL operations
    are FORBIDDEN.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        database_id: The numeric ID of the database to execute the query against.
        sql_query: The SQL INSERT query string to execute.
        schema: Optional schema name for databases that support schemas (e.g., PostgreSQL).

    Returns:
        JSON string containing the execution result, affected row count, and status.
        Returns SqlLabError JSON on failure.

    Examples:
        result = await execute_sql_insert(
            manager, server_id="main", database_id=1,
            sql_query="INSERT INTO users (name, email) VALUES ('John', 'john@example.com')"
        )
        # Returns JSON with affected_rows and status
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_execute_sql_insert", status="error").inc()
        mc.record_error(tool="superset_execute_sql_insert", error_message=f"Server '{server_id}' not found.")
        return SqlLabError(f"Server '{server_id}' not found.", status_code=404).to_json()

    start_time = time.monotonic()
    try:
        validate_insert_query(sql_query)
        validate_dml_query(sql_query, 'superset_execute_sql_insert')

        result = await sqllab_execute_query(
            manager, server_id, database_id, sql_query, schema
        )

        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_execute_sql_insert", status="success").inc()
        mc.tool_duration.labels(tool="superset_execute_sql_insert").observe(
            time.monotonic() - start_time
        )
        mc.queries_executed.labels(source="sql_lab_dml").inc()
        return result

    except ValueError as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_execute_sql_insert", status="error").inc()
        mc.record_error(tool="superset_execute_sql_insert", error_message=str(e))
        return SqlLabError(str(e), status_code=403).to_json()
    except Exception as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_execute_sql_insert", status="error").inc()
        mc.record_error(tool="superset_execute_sql_insert", error_message=str(e))
        return SqlLabError(f"Unexpected error executing SQL: {e}", details=str(e)).to_json()


async def execute_sql_update(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    sql_query: str,
    schema: Optional[str] = None,
) -> str:
    """
    MCP Tool: superset_execute_sql_update - Execute UPDATE statements via Superset SQL Lab.

    Sends an UPDATE query to Superset's SQL Lab engine for execution. Only UPDATE
    statements are allowed. DELETE, INSERT, DROP, CREATE, and all DDL operations
    are FORBIDDEN.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        database_id: The numeric ID of the database to execute the query against.
        sql_query: The SQL UPDATE query string to execute.
        schema: Optional schema name for databases that support schemas (e.g., PostgreSQL).

    Returns:
        JSON string containing the execution result, affected row count, and status.
        Returns SqlLabError JSON on failure.

    Examples:
        result = await execute_sql_update(
            manager, server_id="main", database_id=1,
            sql_query="UPDATE users SET active = false WHERE last_login < '2024-01-01'"
        )
        # Returns JSON with affected_rows and status
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_execute_sql_update", status="error").inc()
        mc.record_error(tool="superset_execute_sql_update", error_message=f"Server '{server_id}' not found.")
        return SqlLabError(f"Server '{server_id}' not found.", status_code=404).to_json()

    start_time = time.monotonic()
    try:
        validate_update_query(sql_query)
        validate_dml_query(sql_query, 'superset_execute_sql_update')

        result = await sqllab_execute_query(
            manager, server_id, database_id, sql_query, schema
        )

        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_execute_sql_update", status="success").inc()
        mc.tool_duration.labels(tool="superset_execute_sql_update").observe(
            time.monotonic() - start_time
        )
        mc.queries_executed.labels(source="sql_lab_dml").inc()
        return result

    except ValueError as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_execute_sql_update", status="error").inc()
        mc.record_error(tool="superset_execute_sql_update", error_message=str(e))
        return SqlLabError(str(e), status_code=403).to_json()
    except Exception as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_execute_sql_update", status="error").inc()
        mc.record_error(tool="superset_execute_sql_update", error_message=str(e))
        return SqlLabError(f"Unexpected error executing SQL: {e}", details=str(e)).to_json()
