"""SQL Lab saved query functionality for Superset MCP integration.

Provides save_sql_query() - saves SQL queries to Superset's Saved
Queries library for later reuse.
"""

import json
import time
import httpx
from typing import Optional, Dict, Any
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.exceptions import SqlLabError
from modules.metrics import get_metrics


async def save_sql_query(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    label: str,
    sql: str,
    schema: Optional[str] = None,
    description: Optional[str] = None
) -> str:
    """
    MCP Tool: superset_save_sql_query - Save a SQL query for later reuse.

    Saves a SQL query to Superset's Saved Queries library so it can be
    re-executed later from the UI or via API. Saved queries are associated
    with a specific database and can include a description.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        database_id: The numeric ID of the database this query targets.
        label: A human-readable name for the saved query.
        sql: The SQL query string to save.
        schema: Optional schema name for the query's database context.
        description: Optional description of what the query does.

    Returns:
        JSON string containing the saved query's details (ID, label, SQL,
        database reference) on success, or SqlLabError JSON on failure.

    Example:
        result = await save_sql_query(
            manager, server_id="main", database_id=1,
            label="Monthly Sales Report", sql="SELECT * FROM public.sales",
            description="Base query for monthly sales analysis"
        )
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_save_sql_query", status="error").inc()
        mc.record_error(tool="superset_save_sql_query", error_message=f"Server '{server_id}' not found.")
        return SqlLabError(f"Server '{server_id}' not found.", status_code=404).to_json()

    start_time = time.monotonic()
    try:
        payload: Dict[str, Any] = {
            "database_id": database_id,
            "label": label,
            "sql": sql,
        }
        if schema:
            payload["schema"] = schema
        if description:
            payload["description"] = description

        endpoint = "/api/v1/saved-query/"
        resp = await execute_request(ctx, "POST", endpoint, json=payload)
        resp.raise_for_status()

        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_save_sql_query", status="success").inc()
        mc.tool_duration.labels(tool="superset_save_sql_query").observe(time.monotonic() - start_time)
        mc.queries_executed.labels(source="saved_query").inc()
        return json.dumps(resp.json(), indent=2)
    except httpx.HTTPStatusError as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_save_sql_query", status="error").inc()
        mc.record_error(tool="superset_save_sql_query", error_message=f"HTTP {e.response.status_code} saving SQL query", status_code=e.response.status_code)
        return SqlLabError(
            f"HTTP {e.response.status_code} saving SQL query",
            status_code=e.response.status_code,
            details=e.response.text,
        ).to_json()
    except Exception as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_save_sql_query", status="error").inc()
        mc.record_error(tool="superset_save_sql_query", error_message=str(e))
        return SqlLabError(f"Unexpected error saving SQL query: {e}", details=str(e)).to_json()
