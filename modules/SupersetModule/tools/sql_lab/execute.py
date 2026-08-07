"""SQL Lab execute query functionality for Superset MCP integration.

Provides sqllab_execute_query() - executes SQL queries via Superset's
SQL Lab engine and returns results as JSON.
"""

import json
import time
import httpx
from typing import Optional, Dict, Any
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.exceptions import SqlLabError
from modules.metrics import get_metrics


async def sqllab_execute_query(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    sql_query: str,
    schema: Optional[str] = None,
    client_id: Optional[str] = None,
    tab_name: Optional[str] = None
) -> str:
    """
    MCP Tool: superset_sqllab_execute_query - Execute a SQL query and get results.

    Sends a SQL query to Superset's SQL Lab engine for execution against a specific
    database. Returns the query results as JSON. For long-running queries, use
    sqllab_get_query_results with the returned client_id to fetch results asynchronously.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        database_id: The numeric ID of the database to execute the query against.
        sql_query: The SQL query string to execute. Must be a valid SELECT statement.
        schema: Optional schema name for databases that support schemas (e.g., PostgreSQL).
        client_id: Optional client ID to track the query. If not provided, Superset
            generates one automatically.
        tab_name: Optional name for the query tab in the SQL Lab UI.

    Returns:
        JSON string containing the query results, metadata (column names, row count),
        and execution details. Returns SqlLabError JSON on failure.

    Example:
        result = await sqllab_execute_query(
            manager, server_id="main", database_id=1,
            sql_query="SELECT * FROM public.sales LIMIT 10"
        )
        # Returns JSON with query results, columns metadata, and client_id for async polling
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_sqllab_execute", status="error").inc()
        mc.record_error(tool="superset_sqllab_execute", error_message=f"Server '{server_id}' not found.")
        return SqlLabError(f"Server '{server_id}' not found.", status_code=404).to_json()

    start_time = time.monotonic()
    try:
        sqllab_payload: Dict[str, Any] = {
            "database_id": database_id,
            "sql": sql_query,
        }
        if schema:
            sqllab_payload["schema"] = schema
        if client_id:
            sqllab_payload["client_id"] = client_id
        if tab_name:
            sqllab_payload["tab_name"] = tab_name

        endpoint = "/api/v1/sqllab/execute/"
        resp = await execute_request(ctx, "POST", endpoint, json=sqllab_payload)
        resp.raise_for_status()

        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_sqllab_execute", status="success").inc()
        mc.tool_duration.labels(tool="superset_sqllab_execute").observe(time.monotonic() - start_time)
        mc.queries_executed.labels(source="sql_lab").inc()
        return json.dumps(resp.json(), indent=2)
    except httpx.HTTPStatusError as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_sqllab_execute", status="error").inc()
        mc.record_error(tool="superset_sqllab_execute", error_message=f"HTTP {e.response.status_code} executing SQL", status_code=e.response.status_code)
        return SqlLabError(
            f"HTTP {e.response.status_code} executing SQL",
            status_code=e.response.status_code,
            details=e.response.text,
        ).to_json()
    except Exception as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_sqllab_execute", status="error").inc()
        mc.record_error(tool="superset_sqllab_execute", error_message=str(e))
        return SqlLabError(f"Unexpected error executing SQL: {e}", details=str(e)).to_json()
